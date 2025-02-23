from .shape import *
from ..utils.fc_view_3d_utils import get_view_direction_by_rot_matrix, get_3d_vertex_for_2d

class Rectangle_Shape(Shape):

    def __init__(self):
        super().__init__()
        self._vertex_ctr.vertices_2d.extend([None, None, None, None])

    def __str__(self):
        return "Rect"

    def can_set_center_type(self):
        return True

    def can_start_from_center(self):
        return True

    def handle_mouse_press(self, mouse_pos_2d, mouse_pos_3d, event, context):

        if mouse_pos_3d is None:
            return 0

        if self.is_none() and event.ctrl:

            if self.get_start_from_center(context):
                self._center_3d = self.get_center(mouse_pos_3d, context)
                self._center_2d = self.vertex_3d_to_2d(context, self._center_3d)
            else:              
                v1 = self.get_center(mouse_pos_3d, context)
                self.set_v2(0, self.vertex_3d_to_2d(context, v1))

            self.state = ShapeState.PROCESSING
            return 0

        elif self.is_processing():
            self.state = ShapeState.CREATED

            self.add_shape_action(Shape_Array_Action("X"))

            self.add_shape_action(Shape_Array_Action())

            self.add_shape_action(Shape_CircleArray_Action())

            self.add_shape_action(Shape_Mirror_Action())

            self.add_shape_action(Shape_Operation_Action())

            self.start_extrude_immediate(mouse_pos_2d, mouse_pos_3d, context)
            return 1

        elif self.is_created() and event.ctrl:
            return 2

        return 0

    def handle_mouse_move(self, mouse_pos_2d, mouse_pos_3d, event, context):

        if self.is_processing():

            # 0-------------1
            # |             |
            # 3-------------2

            if self.get_start_from_center(context):

                cx = self._center_2d[0]
                cy = self._center_2d[1]
                w = mouse_pos_2d[0] - cx
                h = mouse_pos_2d[1] - cy

                self.set_v2(0, (cx - w, cy + h))
                self.set_v2(1, (cx + w, cy + h))
                self.set_v2(2, (cx + w, cy - h))
                self.set_v2(3, (cx - w, cy - h))

            else:

                self.set_v2(2, mouse_pos_2d)
                self.set_v2(1, (self.get_v2(0)[0], self.get_v2(2)[1]))
                self.set_v2(3, (self.get_v2(2)[0], self.get_v2(0)[1]))

                self.calc_center_2d()

            self.create_rect(context)

            self.calc_center_3d(context)
            return True

        result = super().handle_mouse_move(mouse_pos_2d, mouse_pos_3d, event, context)

        return result

    def vertex_moved(self, context):

        self.vertices_3d_to_2d(context)
        self.calc_center_2d()
        self.calc_center_3d(context)

    def vertices_moved(self, diff):
        if self.is_created() and self._is_moving:
            self._center_3d += diff

    def calc_center_2d(self):

        # center = A + 1/2AC
        x = self.get_v2(0)[0] + 0.5 * (self.get_v2(2)[0] - self.get_v2(0)[0] )
        y = self.get_v2(0)[1] + 0.5 * (self.get_v2(2)[1] - self.get_v2(0)[1] )

        self._center_2d = (x, y)

    def calc_center_3d(self, context):
        if self._snap_to_target and self._normal != None:
            self._center_3d = self.get_3d_for_2d(self._center_2d, context)
        else:
            self._center_3d = get_3d_vertex(context, self._center_2d)

    def stop_move(self, context):
        super().stop_move(context)
        self.calc_center_2d()
        # self.calc_center_3d(context)

    def get_gizmo_anchor_vertex(self):
        return self._center_3d

    def create_rect(self, context):
        rv3d = context.space_data.region_3d
        view_rot = rv3d.view_rotation

        self._vertex_ctr.clear_3d()

        # get missing 3d vertices
        if self._snap_to_target and self._normal != None:
            for i in range(4):
                self._vertex_ctr.add_vertex(self.get_3d_for_2d(self.get_v2(i), context))
        else:
            for i in range(4):
                self._vertex_ctr.add_vertex(get_3d_vertex(context, self.get_v2(i)))

        self.create_mirror()
    

    def start_rotate(self, mouse_pos_2d, mouse_pos_3d, context):
        if self.is_created():

            self._is_rotating = True
            self._mouse_y = mouse_pos_2d[1]

            self.vertices_3d_to_2d(context)
            self.calc_center_2d()
            self.calc_center_3d(context)

            return True

        return False

    def get_width(self):
        return (self.get_v3(0) - self.get_v3(3)).length

    def get_height(self):
        return (self.get_v3(0) - self.get_v3(1)).length

    def to_center(self, axis):
        old_center = self._center_3d.copy()
        self.set_center(axis, self._center_3d)

        self.vertices_3d_offset(self._center_3d - old_center)
        self.vertices_3d_to_2d(bpy.context)
        self.calc_center_2d()
        self.calc_center_3d(bpy.context)

        # Bring the array to the center as well
        self.array_offset(self._center_3d - old_center)


    def draw_text(self):

        super().draw_text()
        
        if self.is_processing():

            if self.get_v2(1) is not None:
                self.init_text()

                x = self.get_v2(1)[0]
                y = self.get_v2(1)[1]

                blf.position(2, x + 5, y - 25, 0)
                blf.draw(2, "Width: {0:.3f} | Height: {1:.3f}".format(
                    self.get_width(), self.get_height()))

    def build_actions(self):
        super().build_actions()
        bool_mode = bpy.context.scene.bool_mode
        center_type = bpy.context.scene.center_type

        from_center = "Yes"

        if not bpy.context.scene.start_center:
            from_center = "No"

        self.add_action(Action(self.get_prim_id(),  "Primitive",          "Rectangle"), None)
        self.add_action(Action("O",                 "Operation",           bool_mode),   None)

        mirror_type = bpy.context.scene.mirror_primitive
        self.add_action(Action("M",                 "Mirror",               mirror_type),    ShapeState.NONE)

        # self.add_action(Action("S",                 "Size",               ""),          ShapeState.CREATED)
        self.build_move_action()
        self.add_action(Action("R",                 "Rotate",             ""),          ShapeState.CREATED)
        self.build_extrude_action()
        self.add_action(Action("C",                 "Startpos",            center_type), ShapeState.NONE)
        self.add_action(Action("F",                 "From Center",        from_center),        ShapeState.NONE)
        self.add_action(Action("Left Click",        "Set 2nd point",      ""),          ShapeState.PROCESSING)
        self.add_action(Action("Ctrl + Left Click", "Start",              ""),          ShapeState.NONE)
        self.add_action(Action("Ctrl + Left Click", "Apply",              ""),          ShapeState.CREATED)
        self.add_action(Action("Left Drag",         "Move points",        ""),          ShapeState.CREATED)
        self.add_action(Action("Alt + M",           "To Mesh",            ""),          ShapeState.CREATED)
        self.add_action(Action("Alt + M",           "From Mesh",          ""),          ShapeState.NONE)
        self.add_action(Action("Esc",               self.get_esc_title(), ""),          None)
