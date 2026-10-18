import type { FloorPlan, Point } from '../types/model'
import type { Furniture } from '../stores/projectStore'

function inside(x:number,z:number,ring:Point[]) {
  let result=false
  for(let i=0,j=ring.length-1;i<ring.length;j=i++) {
    const a=ring[i],b=ring[j]
    if((a.z>z)!==(b.z>z)&&x<(b.x-a.x)*(z-a.z)/(b.z-a.z)+a.x)result=!result
  }
  return result
}

export function walkable(x:number,z:number,plan:FloorPlan,furniture:Furniture[],radius=.18) {
  const regions=plan.floor_regions?.length?plan.floor_regions:plan.rooms.map(room=>({points:room.points,holes:[]}))
  // Check the camera circle against actual floor bounds, including courtyards.
  const diagonal=radius/Math.sqrt(2)
  for(const [dx,dz] of [[0,0],[radius,0],[-radius,0],[0,radius],[0,-radius],
                       [diagonal,diagonal],[-diagonal,diagonal],[diagonal,-diagonal],[-diagonal,-diagonal]]) {
    if(!regions.some(r=>inside(x+dx,z+dz,r.points)&&!r.holes.some(h=>inside(x+dx,z+dz,h))))return false
  }
  for(const wall of plan.walls) {
    const dx=wall.end.x-wall.start.x,dz=wall.end.z-wall.start.z,length=Math.hypot(dx,dz)
    const t=((x-wall.start.x)*dx+(z-wall.start.z)*dz)/(length*length)
    const u=Math.max(0,Math.min(1,t)),distance=Math.hypot(x-wall.start.x-u*dx,z-wall.start.z-u*dz)
    if(distance>=wall.thickness/2+radius)continue
    const doorway=plan.doors.some(door=>door.wall_id===wall.id&&door.height>=1.9&&Math.abs((t-door.position)*length)<=door.width/2-radius)
    if(!doorway)return false
  }
  for(const c of plan.columns) {
    const dx=x-c.position.x,dz=z-c.position.z
    if(c.shape==='circular') {if(Math.hypot(dx,dz)<c.width/2+radius)return false}
    else {
      const a=c.rotation??0,localX=Math.cos(a)*dx-Math.sin(a)*dz,localZ=Math.sin(a)*dx+Math.cos(a)*dz
      if(Math.abs(localX)<c.width/2+radius&&Math.abs(localZ)<c.depth/2+radius)return false
    }
  }
  for(const fixture of plan.fixtures??[]) {
    if(fixture.outline.length>=3) {
      if(inside(x,z,fixture.outline))return false
      for(let i=0;i<fixture.outline.length;i++) {
        const a=fixture.outline[i],b=fixture.outline[(i+1)%fixture.outline.length]
        const dx=b.x-a.x,dz=b.z-a.z,length=dx*dx+dz*dz
        const t=length?Math.max(0,Math.min(1,((x-a.x)*dx+(z-a.z)*dz)/length)):0
        if(Math.hypot(x-a.x-dx*t,z-a.z-dz*t)<radius)return false
      }
    }
  }
  for(const f of furniture) {
    const [w,h,d]=f.dimensions??[1,1,1]
    if(f.model==='rug'||h*f.scale[1]<=.06)continue
    const dx=x-f.position[0],dz=z-f.position[2],a=f.rotation[1]
    const localX=Math.cos(a)*dx-Math.sin(a)*dz,localZ=Math.sin(a)*dx+Math.cos(a)*dz
    if(Math.abs(localX)<w*f.scale[0]/2+radius&&Math.abs(localZ)<d*f.scale[2]/2+radius)return false
  }
  return true
}

export function walkSpawn(plan:FloorPlan,furniture:Furniture[]):[number,number,number] {
  const rooms=[...plan.rooms].sort((a,b)=>Number(!/entry|entrada|foyer/i.test(a.name))-Number(!/entry|entrada|foyer/i.test(b.name)))
  for(const room of rooms) {
    if(!room.points.length)continue
    const xs=room.points.map(p=>p.x),zs=room.points.map(p=>p.z)
    const minx=Math.min(...xs),maxx=Math.max(...xs),minz=Math.min(...zs),maxz=Math.max(...zs)
    const cx=(minx+maxx)/2,cz=(minz+maxz)/2
    if(inside(cx,cz,room.points)&&walkable(cx,cz,plan,furniture))return [cx,1.6,cz]
    for(let x=minx+.2;x<maxx;x+=.25)for(let z=minz+.2;z<maxz;z+=.25) {
      if(inside(x,z,room.points)&&walkable(x,z,plan,furniture))return [x,1.6,z]
    }
  }
  return [0,1.6,0]
}
