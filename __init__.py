import bpy
import itertools
from bpy.types import (
    PropertyGroup, UIList, Operator, Panel
)
from bpy.props import (
    PointerProperty, CollectionProperty,
    IntProperty, EnumProperty, FloatVectorProperty
)

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


class MaterialItem(PropertyGroup):
    mat_name: EnumProperty(
        name="Material",
        items=lambda self,ctx: [
            (m.name, m.name, "") for m in bpy.data.materials
        ]
    )
    colors: CollectionProperty(type=ColorItem)
    color_index: IntProperty(default=0)

class MasterSettings(PropertyGroup):
    materials: CollectionProperty(type=MaterialItem)
    mat_index: IntProperty(default=0)


# UILists for Materials & Colors

class BATCH_COLORS_UL_material_list(UIList):
    """List of materials"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=0.7) # reduce width to allow for selection
        split.prop(item, "mat_name", text="")

class BATCH_COLORS_UL_color_list(UIList):
    """List of colors for the selected material"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=0.5) # reduce width to allow for selection
        split.prop(item, "color", text="")  


# Operators to Add/Remove items

class BATCH_COLORS_OT_add_material(Operator):
    bl_idname = "material_list.add_material"
    bl_label = "Add Material"
    def execute(self, context):
        settings = context.scene.batch_settings
        settings.materials.add()
        settings.mat_index = len(settings.materials) - 1
        settings.materials[settings.mat_index].colors.add()  # add a color to the new material
        settings.materials[settings.mat_index].color_index = 0
        return {'FINISHED'}


class BATCH_COLORS_OT_remove_material(Operator):
    bl_idname = "material_list.remove_material"
    bl_label = "Remove Material"
    def execute(self, context):
        settings = context.scene.batch_settings
        settings.materials.remove(settings.mat_index)
        settings.mat_index = max(0, settings.mat_index - 1)
        return {'FINISHED'}


class BATCH_COLORS_OT_add_color(Operator):
    bl_idname = "color_list.add_color"
    bl_label = "Add Color"
    def execute(self, context):
        settings = context.scene.batch_settings
        mat_item = settings.materials[settings.mat_index]
        mat_item.colors.add()
        mat_item.color_index = len(mat_item.colors) - 1
        return {'FINISHED'}


class BATCH_COLORS_OT_remove_color(Operator):
    bl_idname = "color_list.remove_color"
    bl_label = "Remove Color"
    bl_description = "Remove selected color"
    
    # Check to prevent removing the last color
    @classmethod
    def poll(cls, context):
        settings = context.scene.batch_settings
        mat_item = settings.materials[settings.mat_index]
        return mat_item.colors and len(mat_item.colors) > 1
    
    def execute(self, context):
        settings = context.scene.batch_settings
        mat_item = settings.materials[settings.mat_index]
        mat_item.colors.remove(mat_item.color_index)
        mat_item.color_index = max(0, mat_item.color_index - 1)
        return {'FINISHED'}



# TODO: Add a verification step that computes the number of combinations and asks for confirmation before rendering
class BATCH_COLORS_OT_render_batch(Operator):
    """Render all combinations (cartesian product) of material colors.""" 
    bl_idname = "batch.render_combinations"
    bl_description = "Render batch of all color combinations"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Start Batch Render"
    
    combination_count = 0

    def get_color_combinations(self, context):
        "Outputs a touple of two lists: One list of color combinations, and one list of materials"
        settings = context.scene.batch_settings
        
        materials = []
        color_lists = []
        
        # Only add material to render list if it has at least one RGB node
        for mat_item in settings.materials:
            mat = bpy.data.materials.get(mat_item.mat_name)
            if mat and mat.use_nodes:
                nodes = [n for n in mat.node_tree.nodes if n.type=='RGB']
                if not nodes:
                    self.report({'WARNING'}, f"No RGB node found in {mat.name}. Skipping material...")
                else:
                    color_lists.append(mat_item.colors[:])
                    materials.append(mat)
            else:
                self.report({'WARNING'}, f"Error while reading material {mat_item.mat_name}! Skipping...")

        # Cartesian product of color lists
        combos = list(itertools.product(*[color_list for color_list in color_lists]))
        return combos, materials

    def execute(self, context):
        count = 0
        color_combinations, materials = self.get_color_combinations(context = context)

        for combo in color_combinations:
            for mat, color_item in zip(materials, combo):
                # get first RGB node in the material
                rgb_node = next(node for node in mat.node_tree.nodes if node.type=='RGB')
                # set the color of the RGB node
                rgb_node.outputs[0].default_value = color_item.color
                
            # build filepath suffix
            base_path = bpy.context.scene.render.filepath
            suffix = f"_{count:03d}"
            
            bpy.context.scene.render.filepath = f"{base_path}{suffix}.png"
            bpy.ops.render.render(write_still=True)
            bpy.context.scene.render.filepath = base_path  # reset filepath
            count += 1

        return {'FINISHED'}
    
    # Add confirmation dialog before rendering (because total number of combinations can grow very quickly)
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event, message = f"Render batch totalling {len(self.get_color_combinations(context=context)[0])} images (material color combinations)?")


class BATCH_COLORS_PT_batch_render_settings(Panel):
    bl_label = "Batch Render Settings"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"

    def draw(self, context):
        settings = context.scene.batch_settings

        row = self.layout.row(align=True)
        col_materials = row.column()
        col_colors = row.column()

        # Material list + add/remove
        col_materials.template_list(
            "BATCH_COLORS_UL_material_list", "", settings,
            "materials", settings, "mat_index", rows=4
        )
        sub = col_materials.column(align=True)
        sub.operator("material_list.add_material", icon='ADD', text="")
        sub.operator("material_list.remove_material", icon='REMOVE', text="")

        # Colors for selected material
        if settings.materials:
            mat_item = settings.materials[settings.mat_index]
            col_colors.template_list(
                "BATCH_COLORS_UL_color_list", "", mat_item,
                "colors", mat_item, "color_index", rows=4
            )
            sub2 = col_colors.column(align=True)
            sub2.operator("color_list.add_color", icon='ADD', text="")
            sub2.operator("color_list.remove_color", icon='REMOVE', text="")

        self.layout.separator()
        self.layout.operator("batch.render_combinations", icon='RENDER_STILL')

classes = (
    ColorItem, MaterialItem, MasterSettings,
    BATCH_COLORS_UL_material_list, BATCH_COLORS_UL_color_list,
    BATCH_COLORS_OT_add_material, BATCH_COLORS_OT_remove_material,
    BATCH_COLORS_OT_add_color, BATCH_COLORS_OT_remove_color,
    BATCH_COLORS_OT_render_batch, BATCH_COLORS_PT_batch_render_settings
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.batch_settings = PointerProperty(type=MasterSettings)

def unregister():
    del bpy.types.Scene.batch_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
    