import json
import random
import csv
from faker import Faker

def get_user_input_with_prompt(prompt: str, default_value: str) -> str:
    """获取用户输入，如果用户直接回车，则使用默认值。"""
    user_input = input(f"{prompt} (默认: '{default_value}'): ").strip()
    return user_input if user_input else default_value

def generate_realistic_score(full_mark: int, mean_percent: float, std_dev: float) -> int:
    """
    生成一个符合正态分布的、更真实的分数。

    Args:
        full_mark (int): 满分值。
        mean_percent (float): 期望的平均分百分比 (例如 75 表示 75%)。
        std_dev (float): 分数的标准差，值越大分数越分散。

    Returns:
        int: 生成的最终分数。
    """
    mean_score = full_mark * (mean_percent / 100)
    score = random.normalvariate(mean_score, std_dev)
    score = round(max(0, min(score, full_mark)))
    return int(score)

def main():
    """主函数，运行交互式数据生成流程。"""

    print("=" * 50)
    print("🚀 欢迎使用交互式测试数据生成器 (V1.1) 🚀")
    print("=" * 50)
    print("本脚本将引导您生成用于成绩分析的JSON和CSV数据。\n")

    faker = Faker('zh_CN')

    # --- 1. 获取基本配置 ---
    group_name = get_user_input_with_prompt("请输入本次考试的组名（如 2025届高一年级）", "2025届六年级期中考试")

    while True:
        try:
            class_names_str = get_user_input_with_prompt("请输入班级名称列表，用逗号分隔", "一班,二班,三班,四班")
            processed_str = class_names_str.replace('，', ',')
            class_names = [name.strip() for name in processed_str.split(',') if name.strip()]
            if not class_names:
                raise ValueError("班级名称不能为空。")
            break
        except ValueError as e:
            print(f"输入错误: {e} 请重新输入。")

    while True:
        try:
            student_count_range_str = get_user_input_with_prompt("请输入每个班的人数范围，用-连接", "45-55")
            min_students, max_students = map(int, student_count_range_str.split('-'))
            if min_students > max_students or min_students < 1:
                raise ValueError("人数范围设置不正确。")
            break
        except ValueError:
            print("输入格式错误！请输入如 '40-50' 的格式。")

    # --- 2. 获取科目和分数配置 ---
    while True:
        try:
            subjects_str = get_user_input_with_prompt("请输入科目及满分(用:分隔)，科目间用,分隔",
                                                      "语文:100,数学:100,英语:100,科学:100")
            processed_str = subjects_str.replace('，', ',').replace('：', ':')
            full_marks = {item.split(':')[0].strip(): int(item.split(':')[1].strip()) for item in
                          processed_str.split(',')}
            if not full_marks:
                raise ValueError("科目信息不能为空。")
            break
        except (ValueError, IndexError):
            print("输入格式错误！请输入如 '语文:150,数学:150' 的格式。")

    print("\n--- 分数分布设置 ---")
    while True:
        try:
            mean_percent_str = get_user_input_with_prompt("请输入期望的平均分百分比 (如 90 表示平均分为满分的90%)",
                                                          "90")
            mean_percent = float(mean_percent_str)
            if not 0 < mean_percent <= 100:
                raise ValueError("百分比必须在0和100之间。")
            break
        except ValueError:
            print("输入格式错误！请输入一个数字。")

    while True:
        try:
            std_dev_str = get_user_input_with_prompt("请输入分数的标准差 (值越大分数越分散)", "15")
            std_dev = float(std_dev_str)
            if std_dev < 0:
                raise ValueError("标准差不能为负数。")
            break
        except ValueError:
            print("输入格式错误！请输入一个数字。")

    # --- 3. 生成数据 ---
    print("\n⏳ 正在生成数据...")

    final_data = {
        "groupName": group_name,
        "tables": [],
        "fullMarks": full_marks
    }

    csv_rows = []  # 收集 CSV 行

    for class_name in class_names:
        num_students = random.randint(min_students, max_students)
        students_list = []
        for _ in range(num_students):
            student_scores = {}
            for subject, mark in full_marks.items():
                student_scores[subject] = generate_realistic_score(mark, mean_percent, std_dev)

            student_name = faker.name()
            students_list.append({
                "studentName": student_name,
                "scores": student_scores
            })

            # 添加到 CSV 行
            row = {
                "班级": class_name,
                "姓名": student_name,
            }
            row.update(student_scores)
            csv_rows.append(row)

        final_data["tables"].append({
            "tableName": class_name,
            "students": students_list
        })

    print("✅ 数据生成完毕！")

    # --- 4. 输出 JSON 结果 ---
    output_filename = get_user_input_with_prompt("\n请输入要保存的 JSON 文件名 (直接回车则打印到屏幕)",
                                                 "test_data_generated.json")

    output_json = json.dumps(final_data, ensure_ascii=False, indent=2)

    if output_filename:
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(output_json)
            print(f"\n📄 数据已成功保存到 JSON 文件: {output_filename}")
        except IOError as e:
            print(f"\n❌ 保存 JSON 文件失败: {e}")
            print("\n--- JSON 数据输出到屏幕 ---")
            print(output_json)
    else:
        print("\n--- JSON 数据输出到屏幕 ---")
        print(output_json)

    # --- CSV 导出部分 ---
    csv_filename = output_filename.replace('.json', '.csv') if output_filename else "output.csv"
    try:
        fieldnames = ["班级", "姓名"] + list(full_marks.keys())
        with open(csv_filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"📄 数据也已保存为 CSV 文件: {csv_filename} (编码: utf-8-sig)")
    except IOError as e:
        print(f"❌ 保存 CSV 文件失败: {e}")

if __name__ == "__main__":
    main()