import {create} from 'zustand'
import axios, {type InternalAxiosRequestConfig} from 'axios'
import {useProjectStore} from './projectStore'

export interface User {id:string;email:string;name:string;role:'admin'|'member';active:boolean;must_change:boolean}
interface AuthState {
  user:User|null; epoch:number; csrfToken:string|null; loading:boolean; loginAvailable:boolean; accountsReady:boolean; error:string
  refresh:()=>Promise<void>;accept:(data:AuthResponse,broadcast?:boolean)=>void;clear:(broadcast?:boolean)=>void
}
interface AuthResponse {user:User|null;csrf_token:string|null;login_available:boolean;accounts_ready:boolean}
export const AUTH_EVENT='archviz-auth-event'
function notify(type:'login'|'logout',userId?:string){
  try{localStorage.setItem(AUTH_EVENT,JSON.stringify({type,userId,at:Date.now(),nonce:Math.random()}))}catch{/* optional cross-tab notification */}
}
export const useAuthStore=create<AuthState>((set)=>({
  user:null,epoch:0,csrfToken:null,loading:true,loginAvailable:false,accountsReady:false,error:'',
  refresh:async()=>{
    try{const response=await axios.get('/api/v1/auth/session');useAuthStore.getState().accept(response.data)}
    catch(e){if(!axios.isCancel(e))set({loading:false,error:'No se pudo conectar con el servidor. Vuelve a intentarlo.'})}
  },
  accept:(data,broadcast=false)=>{
    const state=useAuthStore.getState(),changed=data.user?.id!==state.user?.id
    const sessionChanged=changed||data.csrf_token!==state.csrfToken
    if(changed)useProjectStore.getState().clearProject()
    set({user:data.user,csrfToken:data.csrf_token,loginAvailable:data.login_available,accountsReady:data.accounts_ready,loading:false,error:'',epoch:state.epoch+(sessionChanged?1:0)})
    if(broadcast)notify('login',data.user?.id)
  },
  clear:(broadcast=true)=>{useProjectStore.getState().clearProject();set(state=>({user:null,csrfToken:null,loading:false,epoch:state.epoch+1}));if(broadcast)notify('logout')},
}))

type AccountRequest=InternalAxiosRequestConfig&{accountEpoch?:number}
axios.interceptors.request.use(config=>{
  (config as AccountRequest).accountEpoch=useAuthStore.getState().epoch
  const token=useAuthStore.getState().csrfToken
  if(token&&!['get','head','options'].includes(config.method??'get')&&config.url?.startsWith('/api/'))config.headers.set('X-CSRF-Token',token)
  return config
})
axios.interceptors.response.use(response=>{
  const config=response.config as AccountRequest
  if(config.url?.startsWith('/api/')&&config.accountEpoch!==useAuthStore.getState().epoch)throw new axios.CanceledError('La sesión cambió durante la solicitud.')
  return response
},error=>{
  const config=error.config as AccountRequest|undefined
  if(config?.url?.startsWith('/api/')&&config.accountEpoch!==useAuthStore.getState().epoch)return Promise.reject(new axios.CanceledError('La sesión cambió durante la solicitud.'))
  if(error.response?.status===401&&error.config?.url?.startsWith('/api/')&&!error.config.url.endsWith('/auth/login')) {
    useAuthStore.getState().clear()
  }
  return Promise.reject(error)
})

export function rememberedProjectKey(){return `archviz-project:${useAuthStore.getState().user?.id??'anonymous'}`}
