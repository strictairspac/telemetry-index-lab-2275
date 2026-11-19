import {workloads,candidates,experiments,voids} from '../api/business.js';
export const store={workloads:[],candidates:[],experiments:[],voids:[],user:null};
export async function refresh(){[store.workloads,store.candidates,store.experiments,store.voids]=await Promise.all([workloads.list(),candidates.list(),experiments.list(),voids.list()]);}
