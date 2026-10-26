import {useEffect, useState, type FormEvent, type ReactNode} from 'react'
import axios from 'axios'
import {Box,LockKeyhole,LogIn} from 'lucide-react'
import {AUTH_EVENT,useAuthStore} from '../stores/authStore'
import {interiorError} from '../utils/interior'

export default function AuthGate({children}:{children:ReactNode}) {
  const {user,loading,error,loginAvailable,accountsReady,refresh}=useAuthStore()
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[newPassword,setNewPassword]=useState(''),[confirm,setConfirm]=useState('')
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('')
  useEffect(()=>{
    void refresh()
    const changed=(event:StorageEvent)=>{
      if(event.key!==AUTH_EVENT||!event.newValue)return
      try{
        const data=JSON.parse(event.newValue)
        if(data.type==='logout'||data.userId!==useAuthStore.getState().user?.id)useAuthStore.getState().clear(false)
        void refresh()
      }catch{/* ignore unrelated browser storage */}
    }
    const restored=(event:PageTransitionEvent)=>{if(event.persisted){useAuthStore.getState().clear(false);void refresh()}}
    window.addEventListener('storage',changed);window.addEventListener('pageshow',restored)
    return ()=>{window.removeEventListener('storage',changed);window.removeEventListener('pageshow',restored)}
  },[refresh])
  const submit=async(event:FormEvent)=>{
    event.preventDefault();setMessage('')
    if(user?.must_change&&newPassword!==confirm){setMessage('Las contraseñas nuevas no coinciden.');return}
    setBusy(true)
    try {
      if(user?.must_change) {
        const response=await axios.post('/api/v1/auth/password',{current_password:password,new_password:newPassword})
        useAuthStore.getState().clear();setPassword('');setNewPassword('');setConfirm('');setMessage(response.data.message)
      }else{
        const response=await axios.post('/api/v1/auth/login',{email,password})
        useAuthStore.getState().accept(response.data,true);setPassword('');setMessage('')
      }
    }catch(e){setMessage(interiorError(e))}finally{setBusy(false)}
  }
  const leave=async()=>{
    setBusy(true)
    try{await axios.post('/api/v1/auth/logout');useAuthStore.getState().clear();setPassword('')}
    catch(e){setMessage(interiorError(e))}finally{setBusy(false)}
  }
  if(user&&!user.must_change)return <>{children}</>
  return <main className="min-h-screen flex items-center justify-center bg-slate-950 px-5 py-10 text-slate-100">
    <section className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-2xl p-7 shadow-2xl space-y-5">
      <div className="flex gap-3 items-center"><div className="rounded-xl p-3 bg-blue-600"><Box size={25}/></div><div><h1 className="font-bold text-2xl">ArchViz Pro</h1><p className="text-slate-400 text-sm">Tu espacio de diseño arquitectónico</p></div></div>
      {loading?<p role="status">Comprobando tu sesión…</p>:error?<><p role="alert" className="text-amber-200 text-sm">{error}</p><button onClick={()=>void refresh()} className="bg-blue-600 rounded-lg p-3 w-full">Volver a intentar</button></>:<>
        <div className="flex items-center gap-2"><LockKeyhole size={20}/><h2 className="text-lg font-semibold">{user?.must_change?'Elige tu contraseña personal':'Iniciar sesión'}</h2></div>
        {!loginAvailable?<p role="status" className="text-sm bg-amber-950/60 text-amber-100 p-4 rounded-lg">El acceso está pendiente de configurar una conexión HTTPS segura. Contacta al administrador para habilitarlo.</p>:!accountsReady?<p role="status" className="text-sm bg-blue-950 p-4 rounded-lg">El administrador debe crear la primera cuenta desde la consola del servidor.</p>:<form onSubmit={submit} className="space-y-4">
          {user?.must_change?<p className="text-sm text-slate-300">Tu cuenta usa una contraseña temporal. Cámbiala para acceder a tus proyectos.</p>:<label className="block text-sm">Correo electrónico<input aria-label="Correo electrónico" type="email" autoComplete="username" maxLength={254} required value={email} onChange={e=>setEmail(e.target.value)} className="block w-full bg-slate-800 border border-slate-600 rounded-lg p-3 mt-1"/></label>}
          <label className="block text-sm">{user?.must_change?'Contraseña temporal':'Contraseña'}<input aria-label={user?.must_change?'Contraseña temporal':'Contraseña'} type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={e=>setPassword(e.target.value)} className="block w-full bg-slate-800 border border-slate-600 rounded-lg p-3 mt-1"/></label>
          {user?.must_change&&<>
            <label className="block text-sm">Contraseña nueva<input aria-label="Contraseña nueva" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={newPassword} onChange={e=>setNewPassword(e.target.value)} className="block w-full bg-slate-800 border border-slate-600 rounded-lg p-3 mt-1"/></label>
            <label className="block text-sm">Repite la contraseña nueva<input aria-label="Repite la contraseña nueva" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirm} onChange={e=>setConfirm(e.target.value)} className="block w-full bg-slate-800 border border-slate-600 rounded-lg p-3 mt-1"/></label>
            <p className="text-xs text-slate-400">Mínimo 12 caracteres. Puedes usar una frase larga.</p>
          </>}
          <button disabled={busy} className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg py-3 w-full font-semibold flex items-center justify-center gap-2"><LogIn size={18}/>{busy?'Procesando…':user?.must_change?'Guardar contraseña':'Entrar'}</button>
        </form>}
        {user?.must_change&&<button disabled={busy} className="text-xs underline text-slate-300" onClick={()=>void leave()}>Cerrar sesión</button>}
        {!user&&loginAvailable&&accountsReady&&<p className="text-xs text-slate-400">Si necesitas una cuenta o recuperar tu contraseña, contacta al administrador.</p>}
        {message&&<p role="status" className="text-sm bg-slate-800 text-amber-100 p-3 rounded-lg">{message}</p>}
      </>}
    </section>
  </main>
}
