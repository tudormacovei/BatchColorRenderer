import bpy
from bpy.props import (
    PointerProperty,
    EnumProperty,
    CollectionProperty,
    IntProperty,
    FloatVectorProperty
)
from bpy.types import Panel, Operator, PropertyGroup, UIList


def get_material_items(self, context):
    return [(mat.name, mat.name, "") for mat in bpy.data.materials]


class ColorItem(PropertyGroup):
    """Contains a color property"""
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        description="Replacement RGBA color"
    )


class BatchRenderSettings(PropertyGroup):
    """Contains all settings for the batch renderer."""
    # currently just contains settings for selecting one material for which different colors will be rendered
    material_name: EnumProperty(
        name="Material",
        description="Choose a material",
        items=get_material_items
    )
    
    # array of colors to cycle through
    colors: CollectionProperty(type=ColorItem)
    
    # currently active color
    active_color_index: IntProperty(
        name="Active Color Index",
        default=0,
        min=0
    )


class MATERIAL_OT_color_add(Operator):
    bl_idname = "material.color_add"
    bl_label = "Add Color"
    bl_description = "Add a new replacement color"

    def execute(self, context):
        settings = context.scene.mat_color_settings
        
        item = settings.colors.add()
        settings.active_color_index = len(settings.colors) - 1
        
        return {'FINISHED'}


class MATERIAL_OT_color_remove(Operator):
    bl_idname = "material.color_remove"
    bl_label = "Remove Color"
    bl_description = "Remove the selected color"

    @classmethod
    def poll(cls, context):
        settings = context.scene.mat_color_settings
        return settings.colors and settings.active_color_index < len(settings.colors)

    def execute(self, context):
        settings = context.scene.mat_color_settings
        
        idx = settings.active_color_index
        settings.colors.remove(idx)
        settings.active_color_index = max(0, idx - 1)
        
        return {'FINISHED'}


class RENDER_OT_render_batch(Operator):
    bl_idname = "render.render_batch"
    bl_label = "Render Batch"
    bl_description = "Render one image for each of the specified colors."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mat_color_settings
        
        mat = bpy.data.materials.get(settings.material_name)
        if not mat or not mat.use_nodes:
            self.report({'ERROR'}, "Invalid material selection or material has no nodes")
            return {'CANCELLED'}

        # TODO: add option to specify wich RGB node to bind to
        # find first RGB node
        rgb_node = None
        for node in mat.node_tree.nodes:
            if node.type == 'RGB':
                rgb_node = node
                break
        if not rgb_node:
            self.report({'ERROR'}, "No RGB node found in material")
            return {'CANCELLED'}

        # TODO: add option for specifying output directory
        base = r"C:/tmp/render"
        # loop over colors
        for idx, item in enumerate(settings.colors):
            # set node color
            rgb_node.outputs[0].default_value = item.color
            # build filepath
            filepath = f"{base}_{idx:03d}.png"
            context.scene.render.filepath = filepath
            self.report({'INFO'}, f"Rendering to {filepath}")
            bpy.ops.render.render(write_still=True)

        return {'FINISHED'}

class MATERIAL_UL_color_swatch(UIList):
    """Custom UIList to display color swatches inline"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # item is a ColorItem
        swatch = layout.split(factor=0.7)
        swatch.prop(item, "color", text="")

class MATERIAL_PT_batch_color(Panel):
    bl_label = "Batch Material Color Picker"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    def draw(self, context):
        settings = context.scene.mat_color_settings

        self.layout.prop(settings, "material_name")

        row = self.layout.row()
        row.template_list(
            "MATERIAL_UL_color_swatch", "material_colors",
            settings, "colors",
            settings, "active_color_index",
            rows=8
        )
        col = row.column(align=True)
        col.operator(MATERIAL_OT_color_add.bl_idname, icon='ADD', text="")
        col.operator(MATERIAL_OT_color_remove.bl_idname, icon='REMOVE', text="")

        self.layout.separator()
        self.layout.operator(RENDER_OT_render_batch.bl_idname, icon='RENDER_STILL')


classes = (
    ColorItem,
    BatchRenderSettings,
    MATERIAL_OT_color_add,
    MATERIAL_OT_color_remove,
    RENDER_OT_render_batch,
    MATERIAL_UL_color_swatch,
    MATERIAL_PT_batch_color
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.mat_color_settings = PointerProperty(type=BatchRenderSettings)
    
def unregister():
    del bpy.types.Scene.mat_color_settings
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
if __name__ == "__main__":
    register()
