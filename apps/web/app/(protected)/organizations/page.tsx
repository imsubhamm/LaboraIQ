import { ResourcePage } from "@/components/resource-page";
export default function Page() { return <ResourcePage title="Organizations" description="Tenant identity and lifecycle configuration." endpoint="organizations" managePermission="organization.manage" emptyMessage="Create the first controlled tenant." columns={[{key:"code",label:"Code"},{key:"name",label:"Organization"},{key:"status",label:"Status"},{key:"updated_at",label:"Last updated"}]} fields={[{name:"name",label:"Organization name",required:true},{name:"code",label:"Organization code",required:true}]}/>; }

