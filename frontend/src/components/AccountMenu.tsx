import {useState,type FormEvent} from 'react'
import axios from 'axios'
import {UserRound,X} from 'lucide-react'
import {useAuthStore,type User,rememberedProjectKey} from '../stores/authStore'
import {useProjectStore} from '../stores/projectStore'
import {loadProject} from '../utils/model'
import {interiorError} from '../utils/interior'

type Project={project_id:string;name:string;revision:number;created_at:string}
export default function AccountMenu() {
  const user=useAuthStore(s=>s.user),recording=useProjectStore(s=>s.recording)
  const [open,setOpen]=useState(false),[tab,setTab]=useState<'projects'|'password'|'users'>('projects')
  const [projects,setProjects]=useState<Project[]>([]),[users,setUsers]=useState<User[]>([])
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('')
  const [name,setName]=useState(''),[email,setEmail]=useState(''),[temporary,setTemporary]=useState('')
  const [oldPassword,setOldPassword]=useState(''),[newPassword,setNewPassword]=useState(''),[confirm,setConfirm]=useState('')
  if(!user)return null
  const run=async(action:()=>Promise<void>)=>{setBusy(true);setMessage('');try{await action()}catch(e){setMessage(interiorError(e))}finally{setBusy(false)}}
  const show=()=>{
    setOpen(!open);setMessage('');setTemporary('');setOldPassword('');setNewPassword('');setConfirm('')
    if(!open){setTab('projects');void run(async()=>{const response=await axios.get('/api/v1/plans');setProjects(response.data.projects)})}
  }
  const openProject=(id:string)=>run(async()=>{
    if(useProjectStore.getState().dirty&&!window.confirm('Hay cambios sin guardar. ¿Descartarlos y abrir esta casa?'))return
    const response=await axios.get(`/api/v1/plans/${id}`);useProjectStore.getState().clearProject();loadProject(response.data);setOpen(false)
  })
  const logout=()=>run(async()=>{
    if(useProjectStore.getState().dirty&&!window.confirm('Hay cambios sin guardar. ¿Cerrar la sesión y descartarlos?'))return
    await axios.post('/api/v1/auth/logout')
    try{localStorage.removeItem(rememberedProjectKey())}catch{/* optional */}
    useAuthStore.getState().clear()
  })
  const password=(event:FormEvent)=>{event.preventDefault();void run(async()=>{
    if(newPassword!==confirm)throw new Error('Las contraseñas nuevas no coinciden.')
    if(useProjectStore.getState().dirty&&!window.confirm('Hay cambios sin guardar. ¿Cambiar la contraseña, cerrar las sesiones y descartarlos?'))return
    await axios.post('/api/v1/auth/password',{current_password:oldPassword,new_password:newPassword})
    useAuthStore.getState().clear()
  })}
  const create=(event:FormEvent)=>{event.preventDefault();void run(async()=>{
    await axios.post('/api/v1/auth/users',{name,email,password:temporary})
    setTemporary('');setName('');setEmail('');const response=await axios.get('/api/v1/auth/users');setUsers(response.data.users)
    setMessage('Cuenta creada. Comparte la contraseña temporal por un canal privado; deberá cambiarla al entrar.')
  })}
  const selectUsers=()=>{setTab('users');void run(async()=>{const response=await axios.get('/api/v1/auth/users');setUsers(response.data.users)})}
  return <>
    <button disabled={recording} onClick={show} className="text-white text-xs rounded-lg border border-white/30 px-3 py-2 flex gap-2 items-center"><UserRound size={16}/>Mi cuenta</button>
    {open&&<div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Mi cuenta">
      <section className="bg-white text-gray-800 rounded-xl p-5 max-w-xl w-full max-h-[90dvh] overflow-y-auto space-y-4">
        <div className="flex justify-between"><div><h2 className="text-lg font-bold">{user.name}</h2><p className="text-xs text-gray-500">{user.email}</p></div><button aria-label="Cerrar mi cuenta" onClick={()=>setOpen(false)}><X size={20}/></button></div>
        <div className="flex gap-2 text-xs"><button onClick={()=>setTab('projects')} className={`border p-2 rounded ${tab==='projects'?'bg-blue-50':''}`}>Mis proyectos</button><button onClick={()=>setTab('password')} className={`border p-2 rounded ${tab==='password'?'bg-blue-50':''}`}>Contraseña</button>{user.role==='admin'&&<button onClick={selectUsers} className={`border p-2 rounded ${tab==='users'?'bg-blue-50':''}`}>Usuarios</button>}</div>
        <fieldset disabled={busy} className="space-y-3 disabled:opacity-50">
        {tab==='projects'&&<><p className="text-xs text-gray-500">Tus casas guardadas, disponibles desde cualquier dispositivo con tu cuenta.</p>{!projects.length&&<p className="text-sm">Todavía no tienes proyectos.</p>}{projects.map(p=><button key={p.project_id} onClick={()=>void openProject(p.project_id)} className="block w-full border rounded p-3 text-left"><span className="text-sm font-semibold">{p.name}</span><span className="block text-xs text-gray-500">Revisión {p.revision} · {new Date(p.created_at).toLocaleDateString()}</span></button>)}</>}
        {tab==='password'&&<form onSubmit={password} className="space-y-3 text-sm">
          <label className="block">Contraseña actual<input aria-label="Contraseña actual" type="password" required autoComplete="current-password" maxLength={128} value={oldPassword} onChange={e=>setOldPassword(e.target.value)} className="block border rounded p-2 w-full mt-1"/></label>
          <label className="block">Contraseña nueva<input aria-label="Contraseña nueva" type="password" required autoComplete="new-password" minLength={12} maxLength={128} value={newPassword} onChange={e=>setNewPassword(e.target.value)} className="block border rounded p-2 w-full mt-1"/></label>
          <label className="block">Repite la contraseña<input aria-label="Repite la contraseña" type="password" required autoComplete="new-password" minLength={12} maxLength={128} value={confirm} onChange={e=>setConfirm(e.target.value)} className="block border rounded p-2 w-full mt-1"/></label>
          <p className="text-xs text-gray-500">Mínimo 12 caracteres. Al cambiarla se cerrarán todas tus sesiones.</p><button className="bg-blue-600 text-white rounded p-2 w-full">Cambiar contraseña</button>
        </form>}
        {tab==='users'&&<>
          <form onSubmit={create} className="space-y-2 text-xs border rounded p-3"><h3 className="font-semibold text-sm">Crear cuenta de cliente o colaborador</h3>
            <label className="block">Nombre<input aria-label="Nombre de la nueva cuenta" required maxLength={100} value={name} onChange={e=>setName(e.target.value)} className="block border rounded p-2 w-full mt-1"/></label>
            <label className="block">Correo<input aria-label="Correo de la nueva cuenta" type="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)} className="block border rounded p-2 w-full mt-1"/></label>
            <label className="block">Contraseña temporal<input aria-label="Contraseña temporal de la nueva cuenta" type="password" required autoComplete="new-password" minLength={12} maxLength={128} value={temporary} onChange={e=>setTemporary(e.target.value)} className="block border rounded p-2 w-full mt-1"/></label>
            <button className="bg-blue-600 text-white rounded p-2 w-full">Crear usuario</button>
          </form>
          {users.map(u=><div key={u.id} className="border rounded p-3 flex gap-2 items-center justify-between text-xs"><div><p className="font-semibold">{u.name}</p><p>{u.email} · {u.role==='admin'?'Administrador':'Usuario'} · {u.active?'Activo':'Desactivado'}</p></div>{u.id!==user.id&&<button className="border rounded p-2" onClick={()=>void run(async()=>{const response=await axios.patch(`/api/v1/auth/users/${u.id}`,{active:!u.active});setUsers(response.data.users)})}>{u.active?'Desactivar':'Activar'}</button>}</div>)}
        </>}
        <button onClick={()=>void logout()} className="text-red-700 border border-red-100 rounded p-2 text-xs w-full">Cerrar sesión</button>
        </fieldset>
        {busy&&<p role="status" className="text-xs">Procesando…</p>}{message&&<p role="status" className="text-xs bg-blue-50 rounded p-3">{message}</p>}
      </section>
    </div>}
  </>
}
