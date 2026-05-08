from pathlib import Path

from report_service import generate_report_with_project_defaults

def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    rendered_docx = generate_report_with_project_defaults(project_root=project_root)
    print("=" * 60)
    print("已生成文档:", rendered_docx)


if __name__ == "__main__":
    main()
