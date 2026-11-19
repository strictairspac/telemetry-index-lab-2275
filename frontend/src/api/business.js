import {api,post} from './client.js';
export const workloads={list:()=>api('/workloads'),save:(d,id)=>post('/workloads'+(id?'/'+id:''),d,id?'PUT':'POST')};
export const candidates={list:()=>api('/candidates'),save:(d,id)=>post('/candidates'+(id?'/'+id:''),d,id?'PUT':'POST')};
export const experiments={list:()=>api('/experiments'),run:d=>post('/experiments',d),detail:id=>api('/experiments/'+id)};
export const voids={list:()=>api('/voids'),preview:d=>post('/voids/preview',d),confirm:d=>post('/voids',d)};
