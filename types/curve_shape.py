from .shape import *

class Curve_Shape(Shape):

    def __init__(self):
        super().__init__()
        self._normals = [None, None]

    def __str__(self):
        return "Curve"

    def can_close(self):
        return self._vertex_ctr.vertex_count >= 2

    def close(self):
            
        if self.can_close():
            self.state = ShapeState.CREATED
            return True
            
        return False

    def connected_shape(self):
        return False

    def connect_to_mouse_pos(self, mouse_pos):
        if self.is_processing():
            return mouse_pos
        return None

    def get_cuts(self):
        return len(self._vertex_ctr.vertices_2d) - 2

    def get_start_point(self):
        if(self.is_created()):
            return self._vertex_ctr.first_vertex
        return None

    def get_end_point(self):
        if(self.is_created()):
            return self._vertex_ctr.last_vertex
        return None

    def get_points(self):
        return self._vertex_ctr.vertices

    def get_normal_start(self):
        return self._normals[0]

    def get_normal_end(self):
        return self._normals[1]

    def handle_mouse_press(self, mouse_pos_2d, mouse_pos_3d, event, context):

        if mouse_pos_3d is None or mouse_pos_2d is None:
            return 0

        scene = context.scene
        region = context.region
        region3D = context.space_data.region_3d

        view_vector = region_2d_to_vector_3d(region,   region3D, mouse_pos_2d)
        origin      = region_2d_to_origin_3d(region,   region3D, mouse_pos_2d)

        # Get intersection with objects
        ray_cast_param = self.get_raycast_param(context.view_layer)
        hit, loc_hit, normal, face, *_ = scene.ray_cast(ray_cast_param, origin, view_vector)
        if hit:
            mouse_pos_3d = loc_hit

        if self.is_none() and event.ctrl:

            # Set startpoint
            self.add_v3(mouse_pos_3d)
            self.add_v2(get_2d_vertex(context, mouse_pos_3d))
            self.state = ShapeState.PROCESSING
            self._normals[0] = normal

        elif self.is_processing() and not event.ctrl and not self.is_2_points_input():
            self.add_v3(mouse_pos_3d)
            self.add_v2(get_2d_vertex(context, mouse_pos_3d))          

        elif self.is_processing() and event.ctrl:

            # Set end point
            self.add_v3(mouse_pos_3d)
            self.add_v2(get_2d_vertex(context, mouse_pos_3d))
            self._normals[1] = normal
            return 1 if self.close() else 0

        return 0

    def handle_mouse_move(self, mouse_pos_2d, mouse_pos_3d, event, context):

        if self.is_processing():
            return True

        result = super().handle_mouse_move(mouse_pos_2d, mouse_pos_3d, event, context)

        return result

    def is_2_points_input(self):
        return bpy.context.scene.curve_input_method == "2-Points"

    def set_next_input_method(self, context):
        context.scene.curve_input_method = next_enum(context.scene.curve_input_method, 
                                                    context.scene, "curve_input_method")

    def build_actions(self):
        curve_2_points = self.is_2_points_input()
        input_method = bpy.context.scene.curve_input_method

        super().build_actions()
        bool_mode = bpy.context.scene.bool_mode
        self.add_action(Action(self.get_prim_id(),  "Primitive",          "Curve"),  None)
        self.add_action(Action("I",                 "Input",       input_method), None)

        self.add_action(Action("Ctrl + Left Click", "Set Startpoint",     ""),       ShapeState.NONE)

        if not curve_2_points:
            self.add_action(Action("Left Click", "Add Point",       ""),       ShapeState.PROCESSING)

        self.add_action(Action("Ctrl + Left Click", "Set Endpoint",       ""),       ShapeState.PROCESSING)
        self.add_action(Action("Alt + M",           "From Mesh",          ""),       ShapeState.NONE)
        self.add_action(Action("Esc",               self.get_esc_title(), ""),       None)