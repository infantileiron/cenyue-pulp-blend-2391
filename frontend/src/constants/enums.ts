export const roles=["admin","analyst","viewer"] as const;
export const runStatuses=["queued","running","completed","infeasible","failed"] as const;
export const reviewStates=["submitted","approved","withdrawn","rejected"] as const;
export const reviewEventLabels:Record<string,string>={
 submit:"提交复核",approve:"批准",withdraw:"撤回",reject:"驳回",resubmit:"修改重提"
};
export const properties=["strength","whiteness","recycled"] as const;
export const propertyLabels:Record<string,string>={strength:"模拟强度指数",whiteness:"白度 %",recycled:"回收纤维率"};
