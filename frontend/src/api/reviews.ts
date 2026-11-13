import {request} from "./client";
export const fetchReviews=()=>request("/reviews");
export const createReviews=(body:unknown)=>request("/reviews","POST",body);
export const decideReview=(id:string,decision:"approve"|"withdraw"|"reject",expected_version:number,comment="")=>
 request("/reviews/"+id+"/"+decision,"POST",{expected_version,comment});
export const resubmitReview=(id:string,action:string)=>
 request("/reviews/"+id+"/resubmit","POST",{action});
export const fetchReviewEvents=(id:string)=>request("/reviews/"+id+"/events");
