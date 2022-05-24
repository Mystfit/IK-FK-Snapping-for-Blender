import bpy
from mathutils import Matrix, Vector
from bl_ui.utils import PresetPanel
from bl_operators.presets import AddPresetBase

bl_info = {
    # required
    'name': 'IK/FK Snapping',
    'blender': (3, 1, 0),
    'category': 'Animation',
    # optional
    'version': (1, 0, 0),
    'author': 'Byron Mallett',
    'description': 'Custom rig FK/IK snapping tools',
}

def arma_items(self, context):
    obs = []
    for ob in context.scene.objects:
        if ob.type == 'ARMATURE':
            obs.append((ob.name, ob.name, ""))
    return obs

def arma_upd(self, context):
    self.arma_coll.clear()
    for ob in context.scene.objects:
        if ob.type == 'ARMATURE':
            item = self.arma_coll.add()
            item.name = ob.name


class MT_LimbPresets(bpy.types.Menu): 
    bl_label = 'Limb Presets' 
    bl_idname = 'MT_LimbPresets'
    preset_subdir = 'object/FKIKSnap_presets' 
    preset_operator = 'script.execute_preset' 
    draw = bpy.types.Menu.draw_preset
    
    
class MY_PT_presets(PresetPanel, bpy.types.Panel):
    bl_label = 'Limb Presets'
    preset_subdir = 'object/FKIKSnap_presets'
    preset_operator = 'script.execute_preset'
    preset_add_operator = 'my.add_preset'


class FKIKSnapPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_fk_to_ik_snap'
    bl_label = 'FK to IK snapping'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'FK/IK Snap'
    
    def draw_header_preset(self, _context): 
        MY_PT_presets.draw_panel_header(self.layout)
    
    def draw(self, context):
        col = self.layout.column()
        row = col.row()
        row.prop(context.scene, "use_frame_range")
        row = col.row()
        row.prop(context.scene, "start_frame")
        row.enabled = context.scene.use_frame_range
        row = row.row()
        row.prop(context.scene, "end_frame")
        row.enabled = context.scene.use_frame_range
        
        if context.scene.FK_control_upper_name and context.scene.FK_control_lower_name:
            snap_ik_to_fk_operator = col.operator('opr.snap_ik_to_fk_operator', text='Snap IK to FK')
        
        if context.scene.IK_control_upper_name and context.scene.IK_control_lower_name:
            snap_fk_to_ik_operator = col.operator('opr.snap_fk_to_ik_operator', text='Snap FK to IK')
            

class FKIKMappingPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_fk_to_ik_mapping'
    bl_label = 'FK/IK bones'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'FK/IK Snap'
    
    def draw_header_preset(self, _context): 
        MY_PT_presets.draw_panel_header(self.layout)
    
    def draw(self, context):
        col = self.layout.column()
        col.prop_search(context.scene, "armature_name", bpy.data, "armatures")
        arma = bpy.data.armatures.get(context.scene.armature_name)
        if arma is not None:
            col.prop_search(context.scene, "FK_control_upper_name", arma, "bones")
            col.prop_search(context.scene, "FK_control_lower_name", arma, "bones")
            col.prop_search(context.scene, "FK_control_end_name", arma, "bones")
            col.prop_search(context.scene, "IK_control_upper_name", arma, "bones")
            col.prop_search(context.scene, "IK_control_lower_name", arma, "bones")
            col.prop_search(context.scene, "IK_control_end_name", arma, "bones")
            col.prop_search(context.scene, "IK_control_name", arma, "bones")
            col.prop_search(context.scene, "IK_control_pole_name", arma, "bones")


class SnapIKToFKOperator(bpy.types.Operator):
    bl_idname = 'opr.snap_ik_to_fk_operator'
    bl_label = 'Snap IK to FK'

    def execute(self, context):
        arma = bpy.data.objects[context.scene.armature_name]
        start_frame = context.scene.start_frame if context.scene.use_frame_range else -1
        end_frame = context.scene.end_frame if context.scene.use_frame_range else -1
        
        if start_frame < 0 or end_frame < 0:
            start_frame = bpy.context.scene.frame_current
            end_frame = start_frame + 1
        
        for frame in range(start_frame, end_frame):
            bpy.context.scene.frame_set(frame)
            self.snap_IK_to_FK(
                arma,
                arma.pose.bones[context.scene.FK_control_upper_name],
                arma.pose.bones[context.scene.FK_control_lower_name],
                arma.pose.bones[context.scene.FK_control_end_name],
                arma.pose.bones[context.scene.IK_control_name],
                arma.pose.bones[context.scene.IK_control_pole_name]
            )
            
            if context.scene.use_frame_range:
                arma.pose.bones[context.scene.IK_control_name].keyframe_insert('location', frame=frame)
                arma.pose.bones[context.scene.IK_control_name].keyframe_insert('rotation_quaternion', frame=frame)
                arma.pose.bones[context.scene.IK_control_pole_name].keyframe_insert('location', frame=frame)
                arma.pose.bones[context.scene.IK_control_pole_name].keyframe_insert('rotation_quaternion', frame=frame)
            
        return {'FINISHED'}
    
    def snap_IK_to_FK(self, armature, FK_upper, FK_lower, FK_end, IK_eff, IK_pole):
        
        # Set IK effector matrix relative to the original FK end bone in armature space
        IK_relative_to_Fk = FK_end.bone.matrix_local.inverted() @ IK_eff.bone.matrix_local
        IK_eff.matrix = FK_end.matrix @ IK_relative_to_Fk
        bpy.context.view_layer.update()
        
        # Get the vector bisecting each FK control (object space)
        PV_normal = ((FK_lower.vector.normalized() + FK_upper.vector.normalized() * -1)).normalized()
        
        # We push the pole control in the opposite direction of the FK bisecting vector (object space)
        PV_matrix_loc = FK_lower.matrix.to_translation() + (PV_normal * -0.2)
        PV_matrix = Matrix.LocRotScale(PV_matrix_loc, IK_pole.matrix.to_quaternion(), None)
        IK_pole.matrix = PV_matrix


class SnapFKtoIKOperator(bpy.types.Operator):
    bl_idname = 'opr.snap_fk_to_ik_operator'
    bl_label = 'Snap FK to IK'

    def execute(self, context):
        arma = bpy.data.objects[context.scene.armature_name]
        start_frame = context.scene.start_frame if context.scene.use_frame_range else -1
        end_frame = context.scene.end_frame if context.scene.use_frame_range else -1
        
        if start_frame < 0 or end_frame < 0:
            start_frame = bpy.context.scene.frame_current
            end_frame = start_frame + 1
        
        for frame in range(start_frame, end_frame):
            bpy.context.scene.frame_set(frame)
            self.snap_FK_to_IK(
                arma.pose.bones[context.scene.IK_control_upper_name],
                arma.pose.bones[context.scene.IK_control_lower_name],
                arma.pose.bones[context.scene.IK_control_end_name],
                arma.pose.bones[context.scene.FK_control_upper_name],
                arma.pose.bones[context.scene.FK_control_lower_name],
                arma.pose.bones[context.scene.FK_control_end_name],
            )
            
            if context.scene.use_frame_range:
                arma.pose.bones[context.scene.FK_control_upper_name].keyframe_insert('location', frame=frame)
                arma.pose.bones[context.scene.FK_control_upper_name].keyframe_insert('rotation_quaternion', frame=frame)
                arma.pose.bones[context.scene.FK_control_lower_name].keyframe_insert('location', frame=frame)
                arma.pose.bones[context.scene.FK_control_lower_name].keyframe_insert('rotation_quaternion', frame=frame)
                arma.pose.bones[context.scene.FK_control_end_name].keyframe_insert('location', frame=frame)
                arma.pose.bones[context.scene.FK_control_end_name].keyframe_insert('rotation_quaternion', frame=frame)
            
        return {'FINISHED'}
    
    def snap_FK_to_IK(self, IK_upper, IK_lower, IK_end, FK_upper, FK_lower, FK_end):
        FK_upper.matrix = IK_upper.matrix
        bpy.context.view_layer.update()
        
        FK_lower.matrix = IK_lower.matrix
        bpy.context.view_layer.update()
        
        FK_relative_to_IK = IK_end.bone.matrix_local.inverted() @ FK_end.bone.matrix_local
        FK_end.matrix = IK_end.matrix @ FK_relative_to_IK
        

class AddLimbPresetOperator(AddPresetBase, bpy.types.Operator):
    bl_idname = 'my.add_preset'
    bl_label = 'Add A preset'
    preset_menu = 'MT_LimbPresets'

    # Common variable used for all preset values
    preset_defines = [
                        'obj = bpy.context.object',
                        'scene = bpy.context.scene'
                     ]

    # Properties to store in the preset
    preset_values = [
                        'scene.armature_name',
                        'scene.FK_control_upper_name',
                        'scene.FK_control_lower_name',
                        'scene.FK_control_end_name',
                        'scene.IK_control_upper_name',
                        'scene.IK_control_lower_name',
                        'scene.IK_control_end_name',
                        'scene.IK_control_name',
                        'scene.IK_control_pole_name'
                    ]

    # Directory to store the presets
    preset_subdir = 'object/FKIKSnap_presets'
    

def register():
    for (prop_name, prop_value) in PROPS:
        setattr(bpy.types.Scene, prop_name, prop_value)
    
    for klass in CLASSES:
        bpy.utils.register_class(klass)


def unregister():
    for (prop_name, _) in PROPS:
        delattr(bpy.types.Scene, prop_name)

    for klass in CLASSES:
        bpy.utils.unregister_class(klass)
        

PROPS = [
    ('armature_search', bpy.props.EnumProperty(items=arma_items, update=arma_upd)),
    ('bone_collection', bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)),
    ('armature_name', bpy.props.StringProperty(name='Armature')),
    ('FK_control_upper_name', bpy.props.StringProperty(name='FK upper')),
    ('FK_control_lower_name', bpy.props.StringProperty(name='FK lower')),
    ('FK_control_end_name', bpy.props.StringProperty(name='FK end')),
    ('IK_control_name', bpy.props.StringProperty(name='IK effector')),
    ('IK_control_pole_name', bpy.props.StringProperty(name='IK pole')),
    ('IK_control_upper_name', bpy.props.StringProperty(name='IK upper')),
    ('IK_control_lower_name', bpy.props.StringProperty(name='IK lower')),
    ('IK_control_end_name', bpy.props.StringProperty(name='IK end')),
    ('use_frame_range', bpy.props.BoolProperty(name='Key across frame range', default=False)),
    ('start_frame', bpy.props.IntProperty(name='Start frame', default=0)),
    ('end_frame', bpy.props.IntProperty(name='End frame', default=0)),
]

CLASSES = [
    SnapIKToFKOperator,
    SnapFKtoIKOperator,
    AddLimbPresetOperator,
    FKIKSnapPanel,
    FKIKMappingPanel,
    MY_PT_presets, 
    MT_LimbPresets
]


if __name__ == '__main__':
    register()
