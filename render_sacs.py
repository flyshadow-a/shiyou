import pyvista as pv
import numpy as np

# =========================
# 统一配色方案
# =========================
COLOR_SCHEME = {
    "background": "white",

    # 结构
    "main_structure": "#E9D012",   # 原结构：暖黄色

    # 节点
    "leg_joint": "#B22222",        # 主腿节点：深红
    "tubular_joint": "#2A7F9E",    # 核心管节点：湖蓝
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
                    # 扩大截取范围，增强对不同版本 SACS 文件的兼容性
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
                try:
                    na = line[7:11].strip()
                    nb = line[11:15].strip()
                    gid = line[15:18].strip()
                    members.append((na, nb, gid))
                except Exception:
                    continue

    print(f"解析结果: 成功读取 {len(nodes)} 个节点, {len(members)} 个构件, {len(groups_od)} 种截面组。")
    return nodes, members, groups_od


def apply_pdf_logic_diagnostic(nodes, members, groups_od, target_z=8.5):
    """
    带有诊断信息输出的算法层
    """
    # 扫描并打印模型中存在的所有 Z 标高
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

    # 扩大容差：筛选出目标标高 (±1.0m 容差) 附近的所有节点
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
            # 判定为主腿 Leg 的条件
            if node_to_max_od[nid] >= local_max_od * 0.95:
                leg_joints.append(nodes[nid])
    else:
        print(f"\n【警告】在标高 {target_z}m (±{tolerance}m) 范围内，没有找到任何节点！请检查上述的标高层列表。")

    # 核心管节点逻辑：连接数 >= 3 的节点
    for nid, neighbors in graph.items():
        if len(neighbors) >= 3:
            tubular_joints.append(nodes[nid])

    return leg_joints, tubular_joints


def visualize(nodes, members, leg_joints, tubular_joints):
    plotter = pv.Plotter()
    plotter.background_color = COLOR_SCHEME["background"]

    node_list = list(nodes.keys())
    id_map = {nid: i for i, nid in enumerate(node_list)}
    points = np.array([nodes[nid] for nid in node_list])

    lines = []
    for na, nb, _ in members:
        if na in id_map and nb in id_map:
            lines.extend([2, id_map[na], id_map[nb]])

    mesh = pv.PolyData(points)
    mesh.lines = np.array(lines)

    # 处理内存溢出 (OOM) 问题
    try:
        # 低精度管状体，减少面片数和内存占用
        structure = mesh.tube(radius=0.15, n_sides=6)
        plotter.add_mesh(
            structure,
            color=COLOR_SCHEME["main_structure"],
            opacity=0.65,
            label="Main Structure"
        )
    except Exception as e:
        # 如果内存依然不够，自动降级为纯线框模式
        print(f"\n【内存警告】生成管状体失败，原因: {e}")
        print("已自动回退为极简线框渲染模式...")
        plotter.add_mesh(
            mesh,
            color=COLOR_SCHEME["main_structure"],
            line_width=2.0,
            opacity=0.85,
            label="Main Structure"
        )

    # 主腿节点
    if leg_joints:
        leg_cloud = pv.PolyData(np.array(leg_joints))
        plotter.add_mesh(
            leg_cloud.glyph(geom=pv.Sphere(radius=0.8), scale=False, orient=False),
            color=COLOR_SCHEME["leg_joint"],
            label="Leg Joint"
        )

    # 核心管节点
    if tubular_joints:
        tub_cloud = pv.PolyData(np.array(tubular_joints))
        plotter.add_mesh(
            tub_cloud.glyph(geom=pv.Sphere(radius=0.3), scale=False, orient=False),
            color=COLOR_SCHEME["tubular_joint"],
            label="Tubular Joint"
        )

    plotter.add_legend(bcolor='white')
    plotter.add_axes()
    plotter.show()


if __name__ == "__main__":
    FILE_PATH = "sacinp.wz6-12 jacket static"

    nodes, members, groups_od = parse_sacs_full_robust(FILE_PATH)

    # 尝试寻找标高 8.5 的节点
    legs, tubulars = apply_pdf_logic_diagnostic(nodes, members, groups_od, target_z=8.5)

    print(f"\n最终识别完成：找到 {len(legs)} 个主腿节点，{len(tubulars)} 个核心管节点。")

    if len(nodes) > 0:
        visualize(nodes, members, legs, tubulars)