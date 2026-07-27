import { ResourcePage } from "@/components/resource-page";
export default function Page() { return <ResourcePage title="Roles" description="Configurable permission bundles and scoped assignments." endpoint="roles" managePermission="role.manage" emptyMessage="Create a role from granular permissions." columns={[{key:"name",label:"Role"},{key:"description",label:"Purpose"},{key:"is_template",label:"Template"},{key:"status",label:"Status"}]} fields={[{name:"name",label:"Role name",required:true},{name:"description",label:"Description"}]}/>; }

