import { ResourcePage } from "@/components/resource-page";

const fields = [
  {name:"name",label:"Department name",required:true},
  {name:"code",label:"Department code",required:true},
  {name:"branch_id",label:"Branch",required:true,lookup:{endpoint:"branches",labelKeys:["name","code"]}},
];

export default function Page() {
  return <ResourcePage title="Departments" description="Configurable laboratory disciplines without clinical rules." endpoint="departments" managePermission="branch.manage" emptyMessage="Add a non-clinical department configuration." columns={[{key:"code",label:"Code"},{key:"name",label:"Department"},{key:"branch_id",label:"Branch"},{key:"status",label:"Status"}]} fields={fields}/>;
}
