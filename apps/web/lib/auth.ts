export type Permission =
  | "organization.read" | "organization.manage"
  | "branch.read" | "branch.manage"
  | "user.read" | "user.manage"
  | "role.read" | "role.manage"
  | "audit.read" | "validation.read" | "validation.manage";

export const developmentPermissions = new Set<Permission>([
  "organization.read", "organization.manage", "branch.read", "branch.manage",
  "user.read", "user.manage", "role.read", "role.manage", "audit.read",
  "validation.read", "validation.manage"
]);

export function can(permission: Permission, permissions = developmentPermissions): boolean {
  return permissions.has(permission);
}

