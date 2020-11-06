from .shape import *

class Polyline_Shape(Shape):

    def __str__(self):
        return "Polyline"

    def can_close(self):
        return len(self._vertices) > 1

    def close(self):
            
        if self.can_close():
            self.state = ShapeState.CREATED
            return True
            
        return False

    def create_from_mesh(self, context):

        obj = context.active_object
        current_mode = obj.mode

        bpy.ops.object.mode_set(mode='EDIT', toggle=False)

        vertices = []

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        
        vert = bm.verts[0]
        prev = None

        for i in range(len(bm.verts)):
            next = None
            for v in [e.other_vert(vert) for e in vert.link_edges if e.is_boundary]:
                if (v != prev):
                    next = v

            if next == None:
                vertices.append(obj.matrix_world @ vert.co)
                break
            
            vertices.append(obj.matrix_world @ vert.co)
            
            prev, vert = vert, next
        
        self.reset()

        for v in vertices:
            self.add_vertex(v)
            self._vertices_2d.append(get_2d_vertex(context, v))
            
        self.close()
        self.build_actions()
        self.create_batch()

        if current_mode is not None:
            bpy.ops.object.mode_set(mode=current_mode, toggle=False)

        return True

    def get_vertices_copy(self, mouse_pos = None):
        result = self._vertices.copy()

        if mouse_pos is not None and self.is_processing():
            result.append(mouse_pos)

        return result

    def get_vertices_mirror_copy(self, mouse_pos = None):
        result = self._vertices_m.copy()

        if mouse_pos is not None and self.is_processing():
            result.append(self.get_vertex_mirror(mouse_pos))

        return result

    def is_draw_input(self, context):
        return context.scene.shape_input_method == "Draw"

    def handle_mouse_press(self, mouse_pos_2d, mouse_pos_3d, event, context):

        super().handle_mouse_press(mouse_pos_2d, mouse_pos_3d, event, context)

        if mouse_pos_3d is None:
            return False

        if self.is_draw_input(context) and event.ctrl and self.state == ShapeState.NONE:
            self.state = ShapeState.PROCESSING
            return False

        if self.is_draw_input(context) and event.ctrl and self.state == ShapeState.PROCESSING:
            if self.close():
                self.start_extrude_immediate(mouse_pos_2d, mouse_pos_3d, context)
            return False

        if (self.is_none() and event.ctrl) or (self.is_processing() and not event.ctrl):

            self.add_vertex(mouse_pos_3d)
            self._vertices_2d.append(get_2d_vertex(context, mouse_pos_3d))
            self.add_vertex_mirror(mouse_pos_3d)

            self.state = ShapeState.PROCESSING
            return False

        elif self.is_processing() and event.ctrl and self.can_close():
            self.add_vertex(mouse_pos_3d)
            self._vertices_2d.append(get_2d_vertex(context, mouse_pos_3d))
            self.add_vertex_mirror(mouse_pos_3d)

            if self.close():
                self.start_extrude_immediate(mouse_pos_2d, mouse_pos_3d, context)
            return False

        elif self.is_created() and event.ctrl:
            return True

        return False

    def handle_mouse_move(self, mouse_pos_2d, mouse_pos_3d, event, context):

        if self.is_draw_input(context):
            if self.state == ShapeState.PROCESSING:
                if len(self._vertices) == 2:
                    self.build_actions()

                self.add_vertex(mouse_pos_3d)
                self._vertices_2d.append(get_2d_vertex(context, mouse_pos_3d))
                return True

        else:
            if self.is_processing():
                return True


        result = super().handle_mouse_move(mouse_pos_2d, mouse_pos_3d, event, context)

        return result

    def get_gizmo_anchor_vertex(self):
        return self._vertices[0]

    def get_point_size(self, context):
        if self.is_draw_input(context):
            return 3
        return super().get_point_size(context)

    def set_next_input_method(self, context):
        context.scene.shape_input_method = next_enum(context.scene.shape_input_method, 
                                                    context.scene, "shape_input_method")

    def build_actions(self):
        super().build_actions()
        bool_mode = bpy.context.scene.bool_mode
        input_method = bpy.context.scene.shape_input_method

        self.add_action(Action(self.get_prim_id(),  "Primitive",   "Polyline"),   None)
        self.add_action(Action("O",                 "Operation",   bool_mode),    None)
        self.add_action(Action("I",                 "Input",       input_method), ShapeState.NONE)
        
        mirror_type = bpy.context.scene.mirror_primitive
        self.add_action(Action("M",                 "Mirror",      mirror_type),    ShapeState.NONE)

        self.build_move_action()
        self.build_extrude_action()

        if not self.is_draw_input(bpy.context):
            self.add_action(Action("Left Click",    "Add line",           ""),          ShapeState.PROCESSING)
        else:
            self.add_action(Action("Move mouse",    "Draw",               ""),          ShapeState.PROCESSING)  

        self.add_action(Action("Ctrl + Left Click", "Start",              ""),          ShapeState.NONE)

        if self.can_close():
            self.add_action(Action("Ctrl + Left Click", "Complete shape",    ""),          ShapeState.PROCESSING)

        self.add_action(Action("Ctrl + Left Click", "Apply",              ""),          ShapeState.CREATED)
        self.add_action(Action("Left Drag",         "Move points",        ""),          ShapeState.CREATED)
        self.add_action(Action("Alt + M",           "To Mesh",            ""),          ShapeState.CREATED)
        self.add_action(Action("Alt + M",           "From Mesh",          ""),          ShapeState.NONE)
        self.add_action(Action("Esc",               self.get_esc_title(), ""),          None)