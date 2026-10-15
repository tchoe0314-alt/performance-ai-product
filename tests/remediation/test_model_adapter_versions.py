"""Canonical version rejects Python bool/numeric equality aliases."""
from copy import deepcopy
import pytest

from backend.services.canonical_record import OWNER, resolve_model_input, seal_record
from backend.services.canonical_project import PROJECT_DOCUMENT_KEY, ProjectDocumentError


@pytest.mark.parametrize("version",[True,False,1.0,"1",None,2])
def test_only_integer_v1_adapter_is_accepted(version):
    record=seal_record({"project_id":"synthetic","name":"Test","project_input":{"manual_fields":{}},"metadata":{},"latest_result":{}})
    source=deepcopy(record["project_input"])
    source[PROJECT_DOCUMENT_KEY]["extensions"][OWNER]["version"]=version
    with pytest.raises(ProjectDocumentError): resolve_model_input(source)
