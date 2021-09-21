# <pep8-80 compliant>
# This product is presented as-is. Edit at your own risk.

# Standard Python Imports
import io
from contextlib import redirect_stdout

# Blender Python Imports
import bpy
from mathutils import Matrix, Vector, geometry

# Addon Info
bl_info = {'name': 'Mirror Weights Closest Point',
           'blender': (2, 90, 3),
           'author': 'Ben Morgan',
           'description': 'A set of operators to mirror weights based on a closest point search.',
           'version': (0, 0, 3),
           'doc_url': 'https://github.com/benmorgantd/bmorgan-blender-addons/blob/main/README.md',
           'tracker_url': 'https://github.com/benmorgantd/bmorgan-blender-addons',
           'category': 'Rigging',
           'location': 'Properties > Object Data Properties > Vertex Group Specials',
           }


#######################################
# Public Global Variables (Okay to edit. Re-install add-on after editing.)
DEFAULT_LEFT_PATTERN = '.l'
DEFAULT_RIGHT_PATTERN = '.r'
# This pattern can be '' if you want to use no identifier for center bones
DEFAULT_CENTER_PATTERN = '.c'
# This width is in meters, so 5cm
DEFAULT_CENTER_BLEND_WIDTH = 0.05
# 0 is YZ, 1 is XZ, 2 is XY
DEFAULT_MIRROR_PLANE_INDEX = 0
# 0 is + to -, 1 is - to +
DEFAULT_MIRROR_DIRECTION_INDEX = 0

#######################################

# Private Global Variables (Do not edit)
_YZ_MIRROR_MATRIX = Matrix()
_YZ_MIRROR_MATRIX[0][0] = -1

_XZ_MIRROR_MATRIX = Matrix()
_XZ_MIRROR_MATRIX[1][1] = -1

_XY_MIRROR_MATRIX = Matrix()
_XY_MIRROR_MATRIX[2][2] = -1

_MIRROR_MATRICES = (_YZ_MIRROR_MATRIX, _XZ_MIRROR_MATRIX, _XY_MIRROR_MATRIX)
_MIRROR_PLANE_NORMALS = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))

_ORIGIN_VECTOR = Vector((0, 0, 0))
_INVERSE_VECTOR = Vector((-1, -1, -1))


def _mirror_vertex_groups(source_mesh,
                          source_vertex_group_names,
                          mirror_plane_index,
                          left_key='.l',
                          right_key='.r',
                          center_key='.c',
                          vertex_mapping_type='POLYINTERP_NEAREST',
                          center_blend_width=0.05,
                          ):
    """Mirrors the given vertex groups, regardless of if the mesh is symmetrical or not, by running a single
    Data Transfer op from a mirrored version of the original mesh. This makes the process much more accurate and fast.

    On center-sided vertex groups (those that contain the given center_key), opposite-sided vertex group weights are
    removed and weights near the mirror plane are linearly blended across that plane if they are within the
    given center_blend_width. This removes artifacts that may occur by doubling up weights near the center.

    This function is expected to be run on a mesh at origin.

    :param bpy.types.Object source_mesh: The mesh containing the vertex group you want to mirror.
    :param list[str] source_vertex_group_names: A list of vertex group names to mirror.
    :param int mirror_plane_index: The index in MIRROR_MATRICES and MIRROR_PLANE_NORMALS to use
    :param str left_key: A string to identify left-sided bones.
    :param str right_key: A string to identify right-sided bones.
    :param str center_key: A string to identify center-sided bones.
    :param str vertex_mapping_type: What mapping method to use when distributing data from closest point searches.
        Pairs with the vert_mapping options in bpy.ops.object.data_transfer
    :param float center_blend_width: The width to use for blending values away from the mirror plane on center bones.
    :return: None
    """

    # The matrix transformation to use when mirroring the duplicate source mesh
    mirror_matrix = _MIRROR_MATRICES[mirror_plane_index]
    # The normal of the mirror plane. Used on center-sided bones.
    mirror_plane_normal = _MIRROR_PLANE_NORMALS[mirror_plane_index]
    # The mix mode for the data transfer is REPLACE on left/right bones and ADD on center bones.
    data_transfer_mix_mode = 'REPLACE'
    # Used to determine if an existing mirror-sided vertex group exists on left/right bones.
    replace_key = (left_key, right_key)

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')

    for source_group_name in source_vertex_group_names:
        if source_group_name.endswith(right_key):
            # Mirror right to left or negative to positive
            replace_key = (right_key, left_key)
            # Invert the mirror plane normal
            mirror_plane_normal *= _INVERSE_VECTOR

        source_group = source_mesh.vertex_groups[source_group_name]

        # Get the mirror name for this vertex group (eg: replace .l with .r)
        mirror_group_name = source_group_name.replace(replace_key[0], replace_key[1])

        if mirror_group_name == source_group_name and center_key in mirror_group_name:
            # Is a center bone.
            data_transfer_mix_mode = 'ADD'
            linear_blend_multiplier_dividend = float(2 * center_blend_width)

            # Zero out the weights on the mirror side, blending them towards the mirror plane.
            for vertex_index in range(len(source_mesh.data.vertices)):
                source_vertex = source_mesh.data.vertices[vertex_index]
                for group_element in source_vertex.groups:
                    if group_element.group == source_group.index:
                        vertex_world_position = (source_mesh.matrix_world @ source_vertex.co)
                        # Get the distance from this vertex to the mirror plane. This can be negative if it is opposite
                        # the given plane's normal.
                        distance_to_mirror_plane = geometry.distance_point_to_plane(vertex_world_position,
                                                                                    _ORIGIN_VECTOR,
                                                                                    mirror_plane_normal)

                        if distance_to_mirror_plane < -center_blend_width:
                            # This vertex is on the mirror side but is outside of the blend width
                            source_group.add([vertex_index], 0.0, 'REPLACE')
                        elif distance_to_mirror_plane < center_blend_width:
                            # This vertex is within the blend width. Blend it between 0 and it's current weight
                            # based on its location relative to the plane's normal.
                            current_weight_value = group_element.weight
                            # If the distance was equal to center_blend_width, the weight multiplier would be 1.
                            # If the distance is equal to 0, the weight multiplier would be 0.5
                            # If the distance is equal to -center_blend_width, the weight multiplier would be 0
                            linear_blend_multiplier = (center_blend_width + distance_to_mirror_plane) / \
                                linear_blend_multiplier_dividend
                            source_group.add([vertex_index], current_weight_value * linear_blend_multiplier, 'REPLACE')

        # Duplicate the source mesh with its modified vertex group weights.
        source_mesh.select_set(True)
        bpy.context.view_layer.objects.active = source_mesh
        bpy.ops.object.duplicate()
        mirrored_mesh = bpy.context.active_object
        # Mirror the duplicated mesh based on our chosen mirror plane
        mirrored_mesh.matrix_world @= mirror_matrix

        # Set the mirror group name active on the source mesh since that is the target of the data transfer.
        source_mesh.vertex_groups.active = source_mesh.vertex_groups[mirror_group_name]
        # Set the source-side vertex group active on the mirror mesh since that is the source of the data transfer.
        mirrored_mesh.vertex_groups.active = mirrored_mesh.vertex_groups[source_group_name]

        bpy.ops.object.select_all(action='DESELECT')
        # Select the target of the data transfer first.
        source_mesh.select_set(True)
        # Select the source of the data transfer second.
        mirrored_mesh.select_set(True)
        bpy.context.view_layer.objects.active = mirrored_mesh

        # Transfer vertex group weights for this group using a closest point search.
        # Values will be interpolated from hit points based on the given vertex_mapping_type.
        # ex: The left arm, mirrored and so overlapping the right arm, will have its weights transferred
        # to the right arm.
        bpy.ops.object.data_transfer(data_type='VGROUP_WEIGHTS',
                                     vert_mapping=vertex_mapping_type,
                                     use_object_transform=True,
                                     use_create=True,
                                     islands_precision=10.0,
                                     ray_radius=1.0,
                                     layers_select_src='ACTIVE',
                                     layers_select_dst='ACTIVE',
                                     mix_mode=data_transfer_mix_mode,
                                     )

        # Quietly delete the mirrored mesh
        bpy.ops.object.select_all(action='DESELECT')
        mirrored_mesh.select_set(True)
        bpy.context.view_layer.objects.active = mirrored_mesh
        with redirect_stdout(io.StringIO()):
            bpy.ops.object.delete()

    # Data Transfer results in a lot of null-value vertex groups on the source mesh. Clean them.
    source_mesh.select_set(True)
    bpy.context.view_layer.objects.active = source_mesh
    bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=0.0)


class MirrorVertexGroupsClosestPointProperties(bpy.types.PropertyGroup):
    """Holds the properties for closest point mirror operations"""

    left_pattern: bpy.props.StringProperty(name='Left Pattern',
                                           default=DEFAULT_LEFT_PATTERN,
                                           description='The pattern to use for identifying left bones',
                                           )

    right_pattern: bpy.props.StringProperty(name='Right Pattern',
                                            default=DEFAULT_RIGHT_PATTERN,
                                            description='The pattern to use for identifying right bones',
                                            )

    center_pattern: bpy.props.StringProperty(name='Center Pattern',
                                             default=DEFAULT_CENTER_PATTERN,
                                             description='The pattern to use for identifying center bones',
                                             )

    mirror_plane: bpy.props.EnumProperty(name='Mirror Plane',
                                         default=DEFAULT_MIRROR_PLANE_INDEX,
                                         description='The plane to mirror weights across',
                                         items=[('0', 'YZ', 'Mirror across the YZ plane'),
                                                ('1', 'XZ', 'Mirror across to XZ plane'),
                                                ('2', 'XY', 'Mirror across to XY plane')],
                                         )

    mirror_direction: bpy.props.EnumProperty(name='Mirror Direction',
                                             default=DEFAULT_MIRROR_DIRECTION_INDEX,
                                             description='The direction to mirror across',
                                             items=[('0', '+ -', 'Mirror positive to negative'),
                                                    ('1', '- +', 'Mirror negative to positive')],
                                             )

    weight_distribution_method: bpy.props.EnumProperty(name='Weight Distribution Method',
                                                       default='POLYINTERP_NEAREST',
                                                       description='The method used to distribute weights after doing '
                                                                   'a closest point on mesh search during mirror and '
                                                                   'weight transfer techniques',
                                                       items=[('POLYINTERP_NEAREST', 'Barycentric',
                                                               'Distribute weights based on '
                                                               'interpolated vertex values '
                                                               'on the hit polygon'),
                                                              ('NEAREST', 'Closest Vertex',
                                                               'Distribute 100% of the source vertex\'s weights to the '
                                                               'closest vertex')],
                                                       )

    center_blend_width: bpy.props.FloatProperty(name='Center Blend Width',
                                                default=DEFAULT_CENTER_BLEND_WIDTH,
                                                description='The distance (in cm) used for the linear blend of weights '
                                                            'near the mirror plane on center-sided bones.')


class MirrorActiveVertexGroupClosestPoint(bpy.types.Operator, MirrorVertexGroupsClosestPointProperties):
    """Mirrors the active vertex group using a closest point on mesh search."""

    bl_idname = "object.bmst_mirror_active_vertex_group_closest_point"
    bl_label = "Mirror Active Vertex Group (Closest Point)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        result = False
        if obj and obj.data and isinstance(obj.data, bpy.types.Mesh):
            if obj.vertex_groups:
                result = True

        return result

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        previous_area = context.area.type
        starting_mode = bpy.context.object.mode
        bpy.context.area.type = 'VIEW_3D'
        source_mesh = context.active_object
        active_vertex_group_name = source_mesh.vertex_groups.active.name

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')

            _mirror_vertex_groups(source_mesh,
                                  [active_vertex_group_name],
                                  int(self.mirror_plane),
                                  left_key=self.left_pattern.strip(),
                                  right_key=self.right_pattern.strip(),
                                  center_key=self.center_pattern.strip(),
                                  vertex_mapping_type=self.weight_distribution_method,
                                  center_blend_width=self.center_blend_width,
                                  )
        finally:
            bpy.context.area.type = previous_area
            bpy.ops.object.mode_set(mode=starting_mode)

        self.report({'INFO'}, 'Finished mirroring vertex group %s on %s' % (active_vertex_group_name, source_mesh.name))
        return {'FINISHED'}


class MirrorAllVertexGroupsClosestPoint(bpy.types.Operator, MirrorVertexGroupsClosestPointProperties):
    """Mirrors all vertex groups using a closest point on mesh search."""

    bl_idname = "object.bmst_mirror_all_vertex_groups_closest_point"
    bl_label = "Mirror All Vertex Groups (Closest Point)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        result = False
        if obj and obj.data and isinstance(obj.data, bpy.types.Mesh) and obj.vertex_groups:
            result = True

        return result

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        previous_area = context.area.type
        starting_mode = bpy.context.object.mode
        bpy.context.area.type = 'VIEW_3D'
        source_mesh = context.active_object
        active_vertex_group_name = source_mesh.vertex_groups.active.name

        if self.mirror_direction == '0':
            vertex_groups = [vg.name for vg in source_mesh.vertex_groups if
                             self.left_pattern in vg.name or self.center_pattern in vg.name]
        else:
            vertex_groups = [vg.name for vg in source_mesh.vertex_groups if
                             self.right_pattern in vg.name or self.center_pattern in vg.name]

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')

            _mirror_vertex_groups(source_mesh,
                                  vertex_groups,
                                  int(self.mirror_plane),
                                  left_key=self.left_pattern.strip(),
                                  right_key=self.right_pattern.strip(),
                                  center_key=self.center_pattern.strip(),
                                  vertex_mapping_type=self.weight_distribution_method,
                                  center_blend_width=self.center_blend_width,
                                  )
        finally:
            bpy.context.area.type = previous_area
            bpy.ops.object.mode_set(mode=starting_mode)
            source_mesh.vertex_groups.active = source_mesh.vertex_groups[active_vertex_group_name]

        self.report({'INFO'}, 'Finished mirroring all vertex groups on %s' % source_mesh.name)
        return {'FINISHED'}


classes = (MirrorActiveVertexGroupClosestPoint,
           MirrorAllVertexGroupsClosestPoint,
           MirrorVertexGroupsClosestPointProperties,
           )


def menu_draw(self, context):
    self.layout.separator()
    self.layout.operator(MirrorActiveVertexGroupClosestPoint.bl_idname,
                         text=MirrorActiveVertexGroupClosestPoint.bl_label,
                         icon='ARROW_LEFTRIGHT')

    self.layout.operator(MirrorAllVertexGroupsClosestPoint.bl_idname,
                         text=MirrorAllVertexGroupsClosestPoint.bl_label,
                         icon='ARROW_LEFTRIGHT')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.MESH_MT_vertex_group_context_menu.append(menu_draw)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.types.MESH_MT_vertex_group_context_menu.remove(menu_draw)


if __name__ == '__main__':
    register()

