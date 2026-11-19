/** @typedef {{id:number,name:string,sensor_id:number,start_at:string,end_at:string,device_type:string|null}} Workload */
/** @typedef {{id:number,name:string,workload_id:number,columns:string[]}} Candidate */
/** @typedef {'valid'|'invalid'|'unverified'|null} ReportState */
/** @typedef {{id:number,name:string,status:'queued'|'running'|'completed'|'failed',result:object|null,report_state:ReportState,invalid_reason:string|null,void_ids:number[]|null}} Experiment */
/** @typedef {{id:number,sensor_id:number,start_at:string,end_at:string,reason:string,actor:string,records:number}} Void */
export {};
