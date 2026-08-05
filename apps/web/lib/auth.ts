export type Permission =
  | "organization.read" | "organization.manage"
  | "branch.read" | "branch.manage"
  | "user.read" | "user.manage"
  | "role.read" | "role.manage"
  | "audit.read" | "validation.read" | "validation.manage"
  | "test_master.read" | "test_master.manage" | "analyzer.read" | "analyzer.manage"
  | "result.read" | "result.review" | "result.validate" | "result.release";

export const developmentPermissions = new Set<Permission>([
  "organization.read", "organization.manage", "branch.read", "branch.manage",
  "user.read", "user.manage", "role.read", "role.manage", "audit.read",
  "validation.read", "validation.manage", "test_master.read", "test_master.manage",
  "analyzer.read", "analyzer.manage",
  "result.read", "result.review", "result.validate", "result.release"
]);

export function can(permission: Permission, permissions = developmentPermissions): boolean {
  return permissions.has(permission);
}
