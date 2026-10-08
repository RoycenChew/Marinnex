/**
 * Aliases over the generated schemas.
 *
 * This file used to hand-write every response shape, because the backend's
 * handlers returned bare dicts and `openapi.json` described their bodies as
 * free-form objects. The handlers now carry Pydantic response models, so the
 * shapes below are **generated**, not transcribed: change the backend, run
 * `npm run gen:api`, and these follow.
 *
 * All that is left here is naming. `components['schemas']['DocumentDetail']`
 * says the same thing as `DocumentDetail` and reads worse everywhere it appears.
 */
import type { components } from './v1'

type Schemas = components['schemas']

export type DocumentStatus =
  | 'processing'
  | 'completed'
  | 'needs_review'
  | 'document_type_mismatch'
  | 'rejected'
  | 'failed'
  | 'unsupported'

export type Evidence = Schemas['EvidenceView']
export type FieldEntry = Schemas['FieldEntry']
export type FieldConfigInput = Schemas['FieldConfigIn']
export type CustomFieldInput = Schemas['CustomFieldIn']
export type CustomFieldView = Schemas['CustomFieldView']
export type ValidationResult = Schemas['ValidationView']
export type Extraction = Schemas['Extraction']
export type PendingAnalysis = Schemas['PendingAnalysis']
export type JobView = Schemas['JobView']
export type DocumentDetail = Schemas['DocumentDetail']
export type DocumentListItem = Schemas['DocumentListItem']
export type DocumentList = Schemas['DocumentList']
export type UploadAccepted = Schemas['UploadAccepted']
export type TemplateField = Schemas['TemplateField']
export type Template = Schemas['Template']
export type SchemaVersion = Schemas['SchemaVersionView']
export type SchemaSummary = Schemas['SchemaView']
export type SchemaCreated = Schemas['SchemaCreated']
export type TestRun = Schemas['TestRun']
export type ApiKey = Schemas['ApiKeyView']
export type CreatedApiKey = Schemas['ApiKeyCreated']
export type Usage = Schemas['Usage']
export type ExportJob = Schemas['ExportJob']
export type Health = Schemas['Health']
export type MeResponse = Schemas['MeResponse']

/** A line-item row inside `Extraction['data']`, which is open by design. */
export type LineItem = Record<string, string | null>
