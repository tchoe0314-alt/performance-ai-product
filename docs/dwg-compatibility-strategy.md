# DWG Compatibility Strategy

Civora does not currently import or export DWG natively. The supported CAD path remains DXF review export, with LandXML exchange data where the model has compatible surface or pipe-network metadata.

## Capability Matrix

| Capability | Current status | Civora behavior |
| --- | --- | --- |
| DXF export | Supported for review when export audit passes | Generates a traceable CAD review artifact from canonical state. |
| LandXML exchange | Contract-level path where compatible data exists | Exposes exchange metadata; target Civil 3D workflow evidence is still required. |
| Civil 3D native package | Not implemented | Civora does not claim native Civil 3D package compatibility. |
| DWG native import/export | Unsupported | Civora does not write or parse DWG files natively. |
| DWG external conversion | Optional architecture only | Requires configured hook plus workflow record before Civora can label a DWG as externally converted for review. |

## Provider Options

The code-level provider list lives in `backend/planning/dwg_compatibility.py` as `DWG_PROVIDER_OPTIONS`.

| Option | Use case | Requirement |
| --- | --- | --- |
| Autodesk Platform Services Design Automation | Convert review artifacts in an Autodesk-hosted workflow | Customer/operator-managed licensing, activity ID, source artifact hash, tool version, workflow record. |
| ODA Drawings SDK | Licensed SDK candidate for DWG write/convert adapters | Separate licensing, deployment validation, layer/unit/block regression fixtures. |
| RealDWG | Autodesk SDK candidate for a native writer path | Separate licensing, runtime validation, repeatable writer tests. |
| Manual CAD workstation workflow | Operator converts DXF/LandXML outside Civora | Attached workflow record with tool/version, source hash, output reference, and limitations. |

## External Conversion Hook

Optional hook metadata can be attached under `meta.dwg_conversion_hook` or `meta.external_conversion_hooks.dwg`:

```json
{
  "enabled": true,
  "provider": "Autodesk Platform Services Design Automation",
  "hook_id": "dwg-converter-v1",
  "source_formats": ["dxf", "landxml"]
}
```

That hook alone does not make DWG supported. A workflow record must also be attached under `meta.external_verification.dwg_conversion`, `meta.external_verification.dwg`, or `meta.dwg_external_conversion_record`:

```json
{
  "result": "passed",
  "tool": "AutoCAD",
  "tool_version": "2026",
  "source_artifact_hash": "hash-rev-2",
  "output_reference": "external-dwg-output-id",
  "notes": "Converted from Civora DXF review artifact."
}
```

When the hook and record are both present, Civora may describe DWG as an externally converted review artifact. It still does not claim native DWG generation or target Civil 3D fidelity.

## Chat And UI Behavior

Expected answers:

| User asks | Civora answer |
| --- | --- |
| “Can I export DWG?” | No native DWG export. Use DXF/LandXML review artifacts, or configure an external hook with a workflow record. |
| “Why is DWG unsupported?” | Civora has no native DWG writer; DWG SDK/provider paths require separate licensing, implementation, and compatibility tests. |
| “What do I need for Civil3D?” | Generate DXF/LandXML review artifacts and attach a target Civil 3D workflow record with tool/version, source hashes, import results, and limitations. |

Public UI copy should continue to say DWG is unsupported natively until a real writer or configured external conversion workflow exists.
