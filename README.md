# blender-closest-point-mirror
A Blender addon for mirroring vertex weights on an asymmetrical mesh by using a closest point data transfer.

## Features
- Fast and accurate mirroring of vertex group weights across topologically asymmetrical meshes.
- Quickly and successfully mirror vertex group weights where Blender's would fail.
- Cleanly blend weights close to the mirror plane to avoid doubling-up of weights.
- Mirror across the YZ, YX, or XZ planes and in either direction
- Ability to modify the width of the center blend
- Ability to change the substrings used to identify left/right/center bones
- Choose between Barycentric and Closest Vertex vertex mapping

## How it Works
The main funcitonality used here is not per-vertex operations. I went down that road initially and it was slow, inaccurate, and resulted in islands of lost data when the mesh was very asymmetrical. 

Instead, this method simply does a targeted data transfer between a duplicated and mirrored version of the original mesh. This makes the technique both fast and accurate, as Blender's data transfer method is great at filling in islands and interpolating data. Mirroring a single vertex group is almost instant, and mirroring all vertex groups on a mesh takes about half a second.

## How to Install It
Install this add-on by going to Edit > Preferences > Add-ons and hitting the Install button. Browse to the python file in this repository called **_bmst_closest_point_mirror.py_**

## How to Use It
These operations have been exposed in the UI in the Vertex Group Specials menu under Properties > Object Data Properties > Vertex Groups
They are called **Mirror Active Vertex Group (Closest Point)** and **Mirror All Vertex Groups (Closest Point)**

Your armature should be at origin and at rest pose before mirroring.

### Calling them Directly
You can also call these operations directly in Python with the following commands:
`bpy.ops.object.bmst_mirror_active_vertex_group_closest_point()`

or

`bpy.ops.object.bmst_mirror_all_vertex_groups_closest_point()`

## More details
Mirrors the given vertex groups, regardless of if the mesh is symmetrical or not, by running a single
Data Transfer op from a mirrored version of the original mesh. This makes the process much more accurate and fast.

On center-sided vertex groups (those that contain the given center_key), opposite-sided vertex group weights are
removed and weights near the mirror plane are linearly blended across that plane if they are within the
given center_blend_width. This removes artifacts that may occur by doubling up weights near the center.

This function is expected to be run on a mesh at origin.

### Parameter Details
- **Left Pattern** : A string to identify left-sided bones.
- **Right Pattern** : A string to identify right-sided bones.
- **Center Pattern** : A string to identify center-sided bones.
- **Mirror Plane** : The plane to mirror across.
- **Mirror Direction** : Determines which side of the mirror plane will be chosen as the source.
- **Weight Distribution Method** : How to distribute weights from hit locations. 
-- `Barycentric` uses a technique that distributes weights based on their relative distance to the vertices of the polygon they hit.
-- `Closest Vertex` distributes 100% of the source vertex's weights to the closest vertex on the hit polygon.
- **Center Blend Width** : The width of the linear blend technique. You may need to adjust this depending on the scale of the mesh you are working on.

Enjoy

Ben Morgan
