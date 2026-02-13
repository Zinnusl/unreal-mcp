from typing import Dict, Any, List, Optional
import unreal
import json


def get_pin_default(pin):
    try:
        default = pin.get_editor_property("default_value")
        if default:
            return str(default)
    except Exception:
        pass
    return None


def get_pin_type_str(pin):
    try:
        pin_type = pin.get_editor_property("pin_type")
        category = str(pin_type.get_editor_property("pin_category"))
        sub_obj = pin_type.get_editor_property("pin_sub_category_object")
        if sub_obj:
            return f"{category}({sub_obj.get_name()})"
        return category
    except Exception:
        return "unknown"


def serialize_pin(pin):
    try:
        direction = str(pin.get_editor_property("direction"))
        is_input = "INPUT" in direction.upper() or "EGPD_INPUT" in direction.upper()
        info = {
            "name": str(pin.get_editor_property("pin_name")),
            "direction": "Input" if is_input else "Output",
            "type": get_pin_type_str(pin),
        }
        default = get_pin_default(pin)
        if default:
            info["default"] = default

        try:
            linked = pin.get_editor_property("linked_to")
            if linked and len(linked) > 0:
                connections = []
                for linked_pin in linked:
                    owner = linked_pin.get_owning_node()
                    connections.append(f"{owner.get_class().get_name()}:{str(linked_pin.get_editor_property('pin_name'))}")
                info["connected_to"] = connections
        except Exception:
            pass

        return info
    except Exception:
        return {"name": "unknown", "direction": "unknown", "type": "unknown"}


def serialize_node(node):
    node_class = node.get_class().get_name()
    info = {
        "class": node_class,
        "name": node.get_name(),
    }

    try:
        comment = node.get_editor_property("node_comment")
        if comment:
            info["comment"] = str(comment)
    except Exception:
        pass

    if node_class == "K2Node_CallFunction":
        try:
            member_ref = node.get_editor_property("function_reference")
            if member_ref:
                member_name = member_ref.get_editor_property("member_name")
                if member_name:
                    info["function"] = str(member_name)
                member_parent = member_ref.get_editor_property("member_parent")
                if member_parent:
                    info["target_class"] = str(member_parent.get_name())
        except Exception:
            pass
    elif node_class == "K2Node_VariableGet" or node_class == "K2Node_VariableSet":
        try:
            var_ref = node.get_editor_property("variable_reference")
            if var_ref:
                info["variable"] = str(var_ref.get_editor_property("member_name"))
        except Exception:
            pass
    elif node_class == "K2Node_Event" or node_class == "K2Node_CustomEvent":
        try:
            if node_class == "K2Node_CustomEvent":
                info["event_name"] = str(node.get_editor_property("custom_function_name"))
            else:
                member_ref = node.get_editor_property("event_reference")
                if member_ref:
                    info["event_name"] = str(member_ref.get_editor_property("member_name"))
        except Exception:
            pass
    elif node_class == "K2Node_MacroInstance":
        try:
            macro_graph = node.get_editor_property("macro_graph_reference")
            if macro_graph:
                info["macro"] = str(macro_graph.get_name())
        except Exception:
            pass

    try:
        pins = node.get_editor_property("pins")
        if pins:
            pin_list = []
            for pin in pins:
                pin_name = str(pin.get_editor_property("pin_name"))
                if pin_name in ("execute", "then", ""):
                    continue
                pin_list.append(serialize_pin(pin))
            if pin_list:
                info["pins"] = pin_list
    except Exception:
        pass

    return info


def serialize_graph(graph):
    graph_info = {
        "name": graph.get_name(),
    }

    try:
        graph_info["class"] = graph.get_class().get_name()
    except Exception:
        pass

    nodes = []
    try:
        graph_nodes = graph.get_editor_property("nodes")
        if graph_nodes:
            for node in graph_nodes:
                nodes.append(serialize_node(node))
    except Exception:
        pass

    graph_info["nodes"] = nodes
    return graph_info


def get_property_info(bp_class):
    properties = []
    try:
        cdo = unreal.get_default_object(bp_class)
        if not cdo:
            return properties

        for prop in bp_class.properties():
            try:
                prop_name = prop.get_name()
                prop_class = prop.get_class().get_name()

                prop_info = {
                    "name": prop_name,
                    "property_class": prop_class,
                }

                try:
                    value = cdo.get_editor_property(prop_name)
                    if value is not None:
                        prop_info["default_value"] = str(value)
                except Exception:
                    pass

                try:
                    if prop.has_any_property_flags(unreal.PropertyFlags.BLUEPRINT_VISIBLE):
                        prop_info["blueprint_visible"] = True
                    if prop.has_any_property_flags(unreal.PropertyFlags.BLUEPRINT_READ_ONLY):
                        prop_info["blueprint_read_only"] = True
                    if prop.has_any_property_flags(unreal.PropertyFlags.EDIT_ANYWHERE):
                        prop_info["edit_anywhere"] = True
                    if prop.has_any_property_flags(unreal.PropertyFlags.NET_REPLICATE):
                        prop_info["replicated"] = True
                except Exception:
                    pass

                properties.append(prop_info)
            except Exception:
                continue
    except Exception:
        pass

    return properties


def get_components(bp):
    components = []
    try:
        scs = bp.get_editor_property("simple_construction_script")
        if scs:
            root_nodes = scs.get_all_nodes()
            for scs_node in root_nodes:
                try:
                    template = scs_node.get_editor_property("component_template")
                    if template:
                        comp_info = {
                            "name": template.get_name(),
                            "class": template.get_class().get_name(),
                        }

                        parent_node = scs_node.get_editor_property("parent_component_or_variable_name")
                        if parent_node:
                            comp_info["parent"] = str(parent_node)

                        components.append(comp_info)
                except Exception:
                    continue
    except Exception:
        pass

    return components


def blueprint_to_text(asset_path: str) -> Dict[str, Any]:
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not asset:
        return {"error": f"Asset not found: {asset_path}"}

    if not isinstance(asset, unreal.Blueprint):
        return {"error": f"Asset is not a Blueprint: {asset_path} (class: {asset.get_class().get_name()})"}

    result = {
        "name": asset.get_name(),
        "path": asset.get_path_name(),
    }

    try:
        gen_class = asset.get_editor_property("generated_class")
        if gen_class:
            result["generated_class"] = gen_class.get_name()
            parent = gen_class.get_super_class()
            if parent:
                result["parent_class"] = parent.get_name()
    except Exception:
        pass

    try:
        bp_type = str(asset.get_editor_property("blueprint_type"))
        result["blueprint_type"] = bp_type
    except Exception:
        pass

    try:
        interfaces = asset.get_editor_property("implemented_interfaces")
        if interfaces and len(interfaces) > 0:
            result["interfaces"] = []
            for iface in interfaces:
                try:
                    iface_class = iface.get_editor_property("interface")
                    if iface_class:
                        result["interfaces"].append(iface_class.get_name())
                except Exception:
                    continue
    except Exception:
        pass

    try:
        gen_class = asset.get_editor_property("generated_class")
        if gen_class:
            props = get_property_info(gen_class)
            if props:
                result["variables"] = props
    except Exception:
        pass

    components = get_components(asset)
    if components:
        result["components"] = components

    graphs = []

    try:
        ubergraph_pages = asset.get_editor_property("ubergraph_pages")
        if ubergraph_pages:
            for graph in ubergraph_pages:
                g = serialize_graph(graph)
                g["graph_type"] = "EventGraph"
                graphs.append(g)
    except Exception:
        pass

    try:
        function_graphs = asset.get_editor_property("function_graphs")
        if function_graphs:
            for graph in function_graphs:
                g = serialize_graph(graph)
                g["graph_type"] = "Function"
                graphs.append(g)
    except Exception:
        pass

    try:
        macro_graphs = asset.get_editor_property("macro_graphs")
        if macro_graphs:
            for graph in macro_graphs:
                g = serialize_graph(graph)
                g["graph_type"] = "Macro"
                graphs.append(g)
    except Exception:
        pass

    if graphs:
        result["graphs"] = graphs

    return result


def main():
    result = blueprint_to_text("${asset_path}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
