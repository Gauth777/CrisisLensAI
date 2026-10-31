import type {Plan} from './types';
export function approvalBlock(plan:Plan):string {
 if(!plan.report_id)return 'No receiving request is attached. This preparedness contribution cannot be approved.';
 if(plan.source_changed)return 'The request changed or is awaiting review. Check the latest request and create a new contribution.';
 if(plan.report_snapshot?.status!=='reviewed')return 'The receiving request is awaiting review.';
 if(plan.resource_check?.conflicts.length)return 'Resolve the conflicting reports before approval.';
 if(plan.report_snapshot?.access_status==='blocked')return 'Access is blocked. Resolve the access report before approval.';
 if(plan.report_snapshot?.demand_status==='not_needed')return 'The receiving site reports no current demand.';
 if(!plan.resources.length&&!plan.volunteers)return 'Add supplies or volunteers in a new contribution before approval.';
 return '';
}
export function submittedAction(event:React.FormEvent<HTMLFormElement>):string {
 const button=(event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement|null;
 return button?.value || 'save';
}
