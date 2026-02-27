from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

class File(BaseModel):
    path: str = Field(description="The path to the file to be created or modified")
    purpose: str = Field(description="The purpose of the file, e.g. 'main application logic', 'data processing module', etc.")
    

class Plan(BaseModel):
    name: str = Field(description="The name of app to be built")
    description: str = Field(description="A one-line description of the app to be built")
    techstack: str = Field(description="The tech stack to be used for the app")
    features: List[str] = Field(description="A list of features that the app should have")
    files: List[File] = Field(description="A list of files to be created")

class ImplementationTask(BaseModel):
    filepath: str = Field(description="The path to the file to be modified")
    task_description: str = Field(description="A detailed description of the task to be performed on the file, e.g. 'add user authentication', 'implement data processing logic', etc.")

class TaskPlan(BaseModel):
    implementation_steps: List[ImplementationTask] = Field(description="A list of steps to be taken to implement the task")
    plan: Optional[Plan] = Field(None, description="The original plan")
    model_config = ConfigDict(extra="allow")

class CoderState(BaseModel):
    task_plan: TaskPlan = Field(description="The plan for the task to be implemented")
    current_step_idx: int = Field(default=0, description="The index of the current step in the implementation steps")
    current_file_content: Optional[str] = Field(None, description="The content of the file currently being edited or created")
    