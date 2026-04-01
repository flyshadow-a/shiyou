import pyvista as pv
import numpy as np

# =========================
# 统一配色方案
# =========================
COLOR_SCHEME = {
    "background": "white",

    # 结构
    "main_structure": "#E9D012",   # 原结构：暖黄色
    "added_structure": "#D95D39",  # 新增结构：砖橙红

    # 节点
    "leg_joint": "#B22222",        # 主腿节点：深红
    "tubular_joint": "#2A7F9E",    # 核心管节点：湖蓝
    "added_node": "#2E8B57",       # 新增节点：深绿
}


def parse_sacs_full_robust(filepath):
    """
    增强版解析器：增加容错处理，防止因文本错位导致丢失节点
    """
    nodes = {}
    members = []
    groups_od = {}

    print(f"\n--- 正在深度解析 SACS 文件: {filepath} ---")

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_idx, line in enumerate(f):
            if line.startswith('GRUP'):
                gid = line[5:8].strip()
                try:
                    od_str = line[14:24].strip()
                    od = float(od_str) if od_str else 0.0
                    groups_od[gid] = od
                except Exception:
                    groups_od[gid] = 0.0

            elif line.startswith('JOINT'):
                try:
                    nid = line[6:10].strip()
                    x = float(line[11:18].strip())
                    y = float(line[18:25].strip())
                    z = float(line[25:32].strip())
                    nodes[nid] = [x, y, z]
                except Exception:
                    continue

            elif line.startswith('MEMBER'):
                # 只解析真正的构件行，跳过 MEMBER OFFSETS
                try:
                    body = line[6:].strip()
                    if body.startswith("OFFSETS"):
                        continue

                    na = line[7:11].strip()
                    nb = line[11:15].strip()
                    gid = line[15:18].strip()

                    if na and nb:
                        members.append((na, nb, gid))
                except Exception:
                    continue

    print(f"解析结果: 成功读取 {len(nodes)} 个节点, {len(members)} 个构件, {len(groups_od)} 种截面组。")
    return nodes, members, groups_od


def apply_pdf_logic_diagnostic(nodes, members, groups_od, target_z=8.5):
    """
    带有诊断信息输出的算法层
    """
    unique_z = sorted(list(set(round(coord[2], 1) for coord in nodes.values())))
    print(f"\n【诊断数据】模型中存在的所有 Z 标高层 (近似值):")
    for i in range(0, len(unique_z), 10):
        print("  ", unique_z[i:i + 10])

    graph = {nid: [] for nid in nodes}
    node_to_max_od = {nid: 0.0 for nid in nodes}

    for na, nb, gid in members:
        if na in nodes and nb in nodes:
            od = groups_od.get(gid, 0.0)
            node_to_max_od[na] = max(node_to_max_od[na], od)
            node_to_max_od[nb] = max(node_to_max_od[nb], od)
            graph[na].append(nb)
            graph[nb].append(na)

    tolerance = 1.0
    elevation_nodes = {
        nid: od for nid, od in node_to_max_od.items()
        if abs(nodes[nid][2] - target_z) < tolerance
    }

    leg_joints = []
    tubular_joints = []

    if elevation_nodes:
        local_max_od = max(elevation_nodes.values())
        print(f"\n【诊断数据】在目标标高 {target_z}m (±{tolerance}m) 范围内，共找到 {len(elevation_nodes)} 个节点。")
        print(f"该层平面的最大截面直径为: {local_max_od}")

        for nid in elevation_nodes:
            if node_to_max_od[nid] >= local_max_od * 0.95:
                leg_joints.append(nodes[nid])
    else:
        print(f"\n【警告】在标高 {target_z}m (±{tolerance}m) 范围内，没有找到任何节点！请检查上述的标高层列表。")

    for nid, neighbors in graph.items():
        if len(neighbors) >= 3:
            tubular_joints.append(nodes[nid])

    return leg_joints, tubular_joints


def normalize_member_key(na, nb, gid):
    """
    将 member 规范化，避免 A-B 与 B-A 被视为不同构件。
    gid 保留，用于区分不同组的同一几何连线。
    """
    a, b = sorted([na, nb])
    return a, b, gid


def split_old_new_structure(old_nodes, old_members, new_nodes, new_members):
    """
    将新模型拆成：
    - 原结构部分
    - 新增结构部分
    """
    old_member_keys = {normalize_member_key(na, nb, gid) for na, nb, gid in old_members}
    new_member_keys = {normalize_member_key(na, nb, gid) for na, nb, gid in new_members}

    added_member_keys = new_member_keys - old_member_keys

    added_members = []
    common_members = []

    for na, nb, gid in new_members:
        key = normalize_member_key(na, nb, gid)
        if key in added_member_keys:
            added_members.append((na, nb, gid))
        else:
            common_members.append((na, nb, gid))

    old_node_ids = set(old_nodes.keys())
    new_node_ids = set(new_nodes.keys())

    added_node_ids = new_node_ids - old_node_ids
    common_node_ids = new_node_ids & old_node_ids

    print(f"\n【差分结果】")
    print(f"原模型节点数: {len(old_node_ids)}")
    print(f"新模型节点数: {len(new_node_ids)}")
    print(f"新增节点数  : {len(added_node_ids)}")
    print(f"原模型构件数: {len(old_members)}")
    print(f"新模型构件数: {len(new_members)}")
    print(f"新增构件数  : {len(added_members)}")

    return {
        "common_members": common_members,
        "added_members": added_members,
        "common_node_ids": common_node_ids,
        "added_node_ids": added_node_ids,
    }


def build_polyline_mesh(nodes, members):
    """
    根据节点和构件生成 PolyData 线模型
    """
    node_ids = list(nodes.keys())
    if not node_ids:
        return None

    id_map = {nid: i for i, nid in enumerate(node_ids)}
    points = np.array([nodes[nid] for nid in node_ids], dtype=float)

    lines = []
    for na, nb, _ in members:
        if na in id_map and nb in id_map:
            lines.extend([2, id_map[na], id_map[nb]])

    if not lines:
        return None

    mesh = pv.PolyData(points)
    mesh.lines = np.array(lines)
    return mesh


def add_structure_mesh(plotter, mesh, color, label, tube_radius=0.15, opacity=0.8):
    """
    给某一类结构加到图中；优先 tube，失败则退回 line 模式
    """
    if mesh is None:
        return

    try:
        structure = mesh.tube(radius=tube_radius, n_sides=6)
        plotter.add_mesh(structure, color=color, opacity=opacity, label=label)
    except Exception as e:
        print(f"\n【内存警告】{label} 生成管状体失败，原因: {e}")
        print(f"已自动回退为线框模式：{label}")
        plotter.add_mesh(mesh, color=color, line_width=2.0, opacity=opacity, label=label)


def add_point_cloud(plotter, points, color, label, radius):
    if not points:
        return
    cloud = pv.PolyData(np.array(points, dtype=float))
    glyph = cloud.glyph(geom=pv.Sphere(radius=radius), scale=False, orient=False)
    plotter.add_mesh(glyph, color=color, label=label)


def visualize_new_model_with_highlight(
    old_nodes,
    new_nodes,
    common_members,
    added_members,
    leg_joints,
    tubular_joints,
    added_node_ids,
):
    plotter = pv.Plotter()
    plotter.background_color = COLOR_SCHEME["background"]

    # 1) 原结构：黄色
    common_mesh = build_polyline_mesh(new_nodes, common_members)
    add_structure_mesh(
        plotter,
        common_mesh,
        color=COLOR_SCHEME["main_structure"],
        label="Original Structure",
        tube_radius=0.12,
        opacity=0.35,
    )

    # 2) 新增结构：砖橙红
    added_mesh = build_polyline_mesh(new_nodes, added_members)
    add_structure_mesh(
        plotter,
        added_mesh,
        color=COLOR_SCHEME["added_structure"],
        label="Added Structure",
        tube_radius=0.20,
        opacity=0.95,
    )

    # 3) 主腿节点：深红
    add_point_cloud(
        plotter,
        leg_joints,
        color=COLOR_SCHEME["leg_joint"],
        label="Leg Joint",
        radius=0.8
    )

    # 4) 核心管节点：湖蓝
    add_point_cloud(
        plotter,
        tubular_joints,
        color=COLOR_SCHEME["tubular_joint"],
        label="Tubular Joint",
        radius=0.3
    )

    # 5) 新增节点：深绿
    added_points = [new_nodes[nid] for nid in added_node_ids if nid in new_nodes]
    add_point_cloud(
        plotter,
        added_points,
        color=COLOR_SCHEME["added_node"],
        label="Added Node",
        radius=0.45
    )

    plotter.add_legend(bcolor='white')
    plotter.add_axes()
    plotter.show()


if __name__ == "__main__":
    OLD_FILE = "sacinp.JKnew"   # 原模型
    NEW_FILE = "sacinp.M1"      # 新模型

    # 读取原模型
    old_nodes, old_members, old_groups_od = parse_sacs_full_robust(OLD_FILE)

    # 读取新模型
    new_nodes, new_members, new_groups_od = parse_sacs_full_robust(NEW_FILE)

    # 新模型上做主腿/核心节点识别
    legs, tubulars = apply_pdf_logic_diagnostic(new_nodes, new_members, new_groups_od, target_z=8.5)

    # 差分：找出新增结构
    split_result = split_old_new_structure(
        old_nodes, old_members,
        new_nodes, new_members
    )

    print(f"\n最终识别完成：")
    print(f"  主腿节点数     : {len(legs)}")
    print(f"  核心管节点数   : {len(tubulars)}")
    print(f"  新增节点数     : {len(split_result['added_node_ids'])}")
    print(f"  新增构件数     : {len(split_result['added_members'])}")

    if len(new_nodes) > 0:
        visualize_new_model_with_highlight(
            old_nodes=old_nodes,
            new_nodes=new_nodes,
            common_members=split_result["common_members"],
            added_members=split_result["added_members"],
            leg_joints=legs,
            tubular_joints=tubulars,
            added_node_ids=split_result["added_node_ids"],
        )