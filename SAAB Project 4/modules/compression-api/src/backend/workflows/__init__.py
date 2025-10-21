# Workflow and Activity Registry
# 
# Replace the example imports and registrations below with your own
# workflows and activities to register them with the Temporal client.
#
# Example:
# from .my_workflows import MyWorkflow, my_activity
# 
# Then add them to the WORKFLOWS and ACTIVITIES lists

from .examples import GreetingWorkflow, compose_greeting
from .compression_workflows import (
    FileCompressionWorkflow,
    update_file_state,
    update_archive_state,
    compress_files,
    mark_files_as_archived,
    delete_files,
)

# Replace with your workflow classes
WORKFLOWS = [
    GreetingWorkflow,
    FileCompressionWorkflow,
]

# Replace with your activity functions
ACTIVITIES = [
    compose_greeting,
    update_file_state,
    update_archive_state,
    compress_files,
    mark_files_as_archived,
    delete_files,
]
