"""Project controller for CRUD behavior."""

from __future__ import annotations

import uuid
from pathlib import Path

from openclaw_gui.app.models.project import Project
from openclaw_gui.app.persistence.repositories import ProjectRepository


class ProjectController:
    """Thin application-facing wrapper around project persistence."""

    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    def list_projects(self) -> list[Project]:
        return self.repository.list_all()

    def create_project(
        self,
        *,
        name: str,
        root_path: str,
        description: str = "",
        default_personality_id: str | None = None,
    ) -> Project:
        if not name.strip():
            raise ValueError("Project name must not be empty.")
        if not Path(root_path).exists():
            raise ValueError(f"Project path does not exist: {root_path}")
        project = Project(
            id=str(uuid.uuid4()),
            name=name.strip(),
            description=description,
            root_path=str(Path(root_path)),
            default_personality_id=default_personality_id,
        )
        return self.repository.create(project)

    def update_project(self, project: Project) -> Project:
        if not project.name.strip():
            raise ValueError("Project name must not be empty.")
        if not Path(project.root_path).exists():
            raise ValueError(f"Project path does not exist: {project.root_path}")
        return self.repository.update(project)

    def delete_project(self, project_id: str) -> None:
        self.repository.delete(project_id)
