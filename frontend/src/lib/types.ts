export type InvoiceStatus =
  | "uploaded"
  | "processing"
  | "ready_for_review"
  | "confirmed"
  | "rejected"
  | "failed";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  country_code: string;
  default_currency: string;
  default_locale: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  locale: string;
  totp_enabled: boolean;
  tenant: Tenant;
}

export interface Supplier {
  id: string;
  name: string;
  vat_number: string | null;
  country_code: string | null;
  city: string | null;
}

export interface InvoiceLine {
  id?: string;
  line_number: number;
  description: string | null;
  quantity: string | null;
  unit_price: string | null;
  vat_rate: string | null;
  line_total_ht: string | null;
  line_total_ttc: string | null;
}

export interface ValidationIssue {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  field?: string | null;
}

export interface ValidationErrors {
  issues: ValidationIssue[];
}

export interface InvoiceDetail {
  id: string;
  tenant_id: string;
  supplier_id: string | null;
  supplier: Supplier | null;
  uploader_user_id: string;
  status: InvoiceStatus;
  invoice_number: string | null;
  issue_date: string | null;
  due_date: string | null;
  currency: string;
  total_ht: string | null;
  total_vat: string | null;
  total_ttc: string | null;
  source_file_name: string;
  source_file_mime: string;
  source_file_size: number;
  source_file_checksum: string;
  ocr_confidence: string | null;
  validation_errors: ValidationErrors | null;
  possible_duplicate_of_id: string | null;
  duplicate_score: string | null;
  duplicate_reason: string | null;
  rejected_reason: string | null;
  paid_at: string | null;
  payment_method: string | null;
  payment_reference: string | null;
  category_id: string | null;
  tags: string[] | null;
  custom_fields: Record<string, unknown> | null;
  approval_status: string;
  approved_by_user_id: string | null;
  approved_at: string | null;
  portal_visible: boolean;
  created_at: string;
  updated_at: string;
  lines: InvoiceLine[];
  file_url: string | null;
}

export interface InvoiceListItem {
  id: string;
  status: InvoiceStatus;
  invoice_number: string | null;
  issue_date: string | null;
  total_ttc: string | null;
  currency: string;
  source_file_name: string;
  created_at: string;
  possible_duplicate_of_id: string | null;
  duplicate_score: string | null;
  paid_at: string | null;
  category_id: string | null;
  tags: string[] | null;
  approval_status: string;
}

export interface InvoiceListResponse {
  items: InvoiceListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface UploadResponse {
  id: string;
  status: InvoiceStatus;
  source_file_name: string;
  source_file_size: number;
}

export interface InvoicePatch {
  invoice_number?: string | null;
  issue_date?: string | null;
  due_date?: string | null;
  currency?: string | null;
  total_ht?: string | null;
  total_vat?: string | null;
  total_ttc?: string | null;
  paid_at?: string | null;
  payment_method?: string | null;
  payment_reference?: string | null;
  category_id?: string | null;
  tags?: string[] | null;
  custom_fields?: Record<string, unknown> | null;
  lines?: InvoiceLine[];
}

export interface Correction {
  id: string;
  user_id: string | null;
  field: string;
  before_value: string | null;
  after_value: string | null;
  created_at: string;
}

export interface InvoiceStats {
  counters: Record<string, number>;
}

export type EmailProvider = "outlook" | "gmail";

export type CloudDriveProvider = "gdrive" | "dropbox" | "onedrive";

export interface CloudDriveSource {
  id: string;
  provider: CloudDriveProvider;
  account_email: string | null;
  folder_id: string;
  folder_name: string | null;
  is_active: boolean;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface EmailSource {
  id: string;
  provider: EmailProvider;
  account_email: string;
  folder: string;
  is_active: boolean;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface AuthorizeResponse {
  authorize_url: string;
}

export type MyDataConnectorKind = "epsilon_digital" | "softone_mydata" | "aade_direct";

export interface MyDataConnector {
  id: string;
  kind: MyDataConnectorKind;
  base_url: string;
  issuer_vat_number: string | null;
  auto_submit: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MyDataConnectorInput {
  kind: MyDataConnectorKind;
  base_url: string;
  credentials: Record<string, string>;
  issuer_vat_number?: string | null;
  auto_submit: boolean;
  is_active: boolean;
}

export type MyDataSubmissionStatus =
  | "pending"
  | "submitted"
  | "acknowledged"
  | "failed"
  | "cancelled";

export interface MyDataSubmission {
  id: string;
  invoice_id: string;
  status: MyDataSubmissionStatus;
  external_id: string | null;
  aade_mark: string | null;
  uid: string | null;
  error_message: string | null;
  retry_count: number;
  submitted_at: string | null;
  acknowledged_at: string | null;
  created_at: string;
  updated_at: string;
}

export type ErpConnectorKind = "softone" | "epsilon_net";

export interface ErpConnector {
  id: string;
  kind: ErpConnectorKind;
  base_url: string;
  auto_export: boolean;
  is_active: boolean;
  config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ErpConnectorInput {
  kind: ErpConnectorKind;
  base_url: string;
  credentials: Record<string, string>;
  config?: Record<string, unknown> | null;
  auto_export: boolean;
  is_active: boolean;
}

export type ErpExportStatus =
  | "pending"
  | "submitted"
  | "acknowledged"
  | "failed"
  | "cancelled";

export interface ErpExport {
  id: string;
  invoice_id: string;
  status: ErpExportStatus;
  external_id: string | null;
  error_message: string | null;
  retry_count: number;
  submitted_at: string | null;
  acknowledged_at: string | null;
  created_at: string;
  updated_at: string;
}

export type UserRole = "admin" | "reviewer" | "viewer" | "user";

export interface TenantUser {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface UserCreatePayload {
  email: string;
  full_name?: string | null;
  role: UserRole;
}

export interface UserCreatedResponse {
  user: TenantUser;
  activation_link: string | null;
}

export interface InvoiceCategory {
  id: string;
  name: string;
  color: string | null;
  gl_code: string | null;
}

export interface InvoiceComment {
  id: string;
  invoice_id: string;
  user_id: string | null;
  body: string;
  mentions: string[] | null;
  created_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface UserSession {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  last_seen_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface AuditLog {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
}
