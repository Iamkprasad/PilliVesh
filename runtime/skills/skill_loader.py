from pathlib import Path

SKILLS_DIR = Path(__file__).parent


def list_skills():
    return sorted(
        p.name
        for p in SKILLS_DIR.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists()
    )


def load_skill(name):
    path = SKILLS_DIR / name / "SKILL.md"

    if not path.exists():
        raise ValueError(f"Skill not found: {name}")

    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    print("Available skills:", list_skills())
