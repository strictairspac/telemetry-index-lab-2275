import {STATUSES,REPORT_STATES} from '../../constants/enums.js';
export const status=s=>`<span class="status ${s}">${STATUSES[s]||s}</span>`;
export const reportStatus=s=>s?`<span class="status report ${s}">${REPORT_STATES[s]||s}</span>`:'';
