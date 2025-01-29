import bpy

from mathutils import Vector

class VertexData(bpy.types.PropertyGroup):
    position: bpy.props.FloatVectorProperty(
        name="Position",
        description="Coordinates of the vertex",
        size=3,
        default=(0.0, 0.0, 0.0)
    )

class ShapeType(bpy.types.PropertyGroup):
    CIRCLE = 'CIRCLE'
    RECTANGLE = 'RECTANGLE'
    POLYGON = 'POLYGON'

class ShapeData(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(default="Shape")
    vertices: bpy.props.CollectionProperty(type=VertexData)
    shape_type: bpy.props.EnumProperty(
        name="Shape Type",
        description="Type of the shape",
        items=[
            (ShapeType.CIRCLE, "Circle", ""),
            (ShapeType.RECTANGLE, "Rectangle", ""),
            (ShapeType.POLYGON, "Polygon", "")
        ],
        default=ShapeType.POLYGON
    )
