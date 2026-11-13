export type Role="admin"|"analyst"|"viewer";
export interface User{email:string;role:Role}
export interface Entity{id:string;created_at:string;[key:string]:any}
export interface Share{material_id:string;name:string;share:number;unit_cost:number;min_share:number;max_share:number}
export interface Quality{property:string;value:number;minimum:number;maximum:number;lower_slack:number;upper_slack:number}
export type ReviewState="submitted"|"approved"|"withdrawn"|"rejected";
export type ReviewEventAction="submit"|"approve"|"withdraw"|"reject"|"resubmit";
export interface ReviewEvent{
 id:string;created_at:string;review_id:string;
 action:ReviewEventAction;from_state:string;to_state:string;
 actor:string;comment:string;detail:{version?:number};
}
export interface FormulaReview extends Entity{
 run_id:string;action:string;state:ReviewState;reviewer:string;
 version:number;created_by:string;events:ReviewEvent[];
}
