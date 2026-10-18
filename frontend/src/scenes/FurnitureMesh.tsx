import { RoundedBox } from '@react-three/drei'
import * as THREE from 'three'
import { useProjectStore, type Furniture } from '../stores/projectStore'

export default function FurnitureMesh({item,woodTexture}:{item:Furniture;woodTexture:THREE.Texture}) {
  const selected=useProjectStore(s=>s.selectedFurnitureId===item.id)
  const [w,h,d]=item.dimensions??[1,1,1]
  const color=item.color||'#c7b499'
  const finish=useProjectStore(s=>s.floorPlan?.interior_style)
  const wood=finish?.wood??'#a98c68',accent=finish?.accent??'#414b44'
  const model=item.model||(item.category==='bed'?'bed_queen':item.category==='seating'?'sofa':item.category==='table'?'coffee_table':'dresser')
  const rounded=(size:[number,number,number],position:[number,number,number],tint=color,radius=.04)=>
    <RoundedBox args={size} position={position} radius={Math.min(radius,...size.map(n=>n/3))} smoothness={2}>
      <meshStandardMaterial color={tint} roughness={item.material==='metal'?.35:.83} metalness={item.material==='metal'?.5:0}/>
    </RoundedBox>
  const block=(size:[number,number,number],position:[number,number,number],tint=wood,grain=true)=><mesh position={position}>
    <boxGeometry args={size}/><meshStandardMaterial color={tint} map={grain?woodTexture:null} roughness={.68}/>
  </mesh>
  const legs=(top:number,inset=.1)=><>{[-1,1].flatMap(x=>[-1,1].map(z=><mesh key={`${x}${z}`} position={[x*(w/2-inset),top/2,z*(d/2-inset)]}>
    <cylinderGeometry args={[.025,.018,top,8]}/><meshStandardMaterial color={wood} roughness={.7}/>
  </mesh>))}</>
  let contents
  if(['sofa','outdoor_sofa','armchair'].includes(model)) {
    const arms=Math.min(.14,w*.13)
    contents=<>
      {legs(h*.18)}{rounded([w,h*.23,d],[0,h*.29,0],wood)}
      {rounded([w-arms*2,h*.18,d*.78],[0,h*.49,d*.04])}
      {rounded([w,h*.56,d*.19],[0,h*.72,-d*.4])}
      {[-1,1].map(side=><group key={side}>{rounded([arms,h*.39,d*.9],[side*(w-arms)/2,h*.56,0])}</group>)}
      {(w>1.2?[-.25,.25]:[0]).map((x,i)=><group key={i}>{rounded([w*(w>1.2?.38:.68),h*.27,d*.16],[x*w,h*.75,-d*.24],i?accent:color)}</group>)}
    </>
  } else if(model.startsWith('bed_')) {
    contents=<>
      {legs(h*.13)}{block([w,h*.22,d],[0,h*.23,0])}
      {rounded([w*.96,h*.20,d*.94],[0,h*.43,0],'#f0ede4',.07)}
      {rounded([w,h*.88,.09],[0,h*.56,-d*.47],wood)}
      {rounded([w*.98,h*.035,d*.63],[0,h*.55,d*.13])}
      {[-1,1].map(side=><group key={side}>{rounded([w*.4,h*.09,d*.17],[side*w*.245,h*.58,-d*.29],'#faf8f0',.06)}</group>)}
      {rounded([w*.99,h*.035,d*.16],[0,h*.575,d*.34],accent)}
    </>
  } else if(['dining_chair','stool'].includes(model)) {
    contents=<>
      {legs(h*.52,.065)}{rounded([w,h*.10,d],[0,h*.57,0])}
      {model!=='stool'&&rounded([w*.96,h*.39,d*.11],[0,h*.805,-d*.43])}
    </>
  } else if(['coffee_table','side_table','desk','dining_table'].includes(model)) {
    contents=<>{legs(h*.92,.075)}{rounded([w,h*.08,d],[0,h*.96,0],color,.025)}</>
  } else if(model==='rug') {
    contents=<>{rounded([w,h,d],[0,h/2,0],color,.01)}{[-1,1].map(side=><group key={side}>{block([w*.94,.002,d*.018],[0,h+.002,side*d*.41],accent,false)}</group>)}</>
  } else if(model==='floor_lamp') {
    contents=<>
      <mesh position={[0,.025,0]}><cylinderGeometry args={[w*.42,w*.45,.05,24]}/><meshStandardMaterial color={accent} metalness={.5} roughness={.35}/></mesh>
      <mesh position={[0,h*.46,0]}><cylinderGeometry args={[.015,.015,h*.88,12]}/><meshStandardMaterial color={accent} metalness={.6}/></mesh>
      <mesh position={[0,h*.89,0]}><cylinderGeometry args={[w*.31,w*.5,h*.22,24]}/><meshStandardMaterial color="#f1e6cf" side={THREE.DoubleSide}/></mesh>
    </>
  } else if(model==='plant') {
    contents=<>
      <mesh position={[0,h*.15,0]}><cylinderGeometry args={[w*.34,w*.25,h*.3,20]}/><meshStandardMaterial color={wood}/></mesh>
      <mesh position={[0,h*.5,0]}><cylinderGeometry args={[.012,.02,h*.55,8]}/><meshStandardMaterial color="#536143"/></mesh>
      {[0,1,2,3,4].map(i=><group key={i} position={[0,h*(.42+i*.09),0]} rotation={[0,i*2.4,0]}>
        <mesh position={[w*.17,0,0]} rotation={[0,0,-.45]} scale={[w*.38,h*.2,d*.12]}><sphereGeometry args={[1,10,8]}/><meshStandardMaterial color={i%2?'#6b8c51':'#3e6849'} roughness={.9}/></mesh>
      </group>)}
    </>
  } else if(model==='toilet') {
    contents=<>
      {rounded([w*.58,h*.52,d*.7],[0,h*.26,d*.07],'#ebece7')}
      {rounded([w,h*.2,d*.7],[0,h*.57,d*.12],'#fafaf5')}
      {rounded([w*.85,h*.42,d*.24],[0,h*.79,-d*.36],'#f6f6ef')}
      <mesh position={[0,h*.68,d*.12]} rotation={[-Math.PI/2,0,0]} scale={[w*.34,d*.25,1]}><ringGeometry args={[.68,1,24]}/><meshStandardMaterial color="#e0e3dc" side={THREE.DoubleSide}/></mesh>
    </>
  } else if(model==='bathtub') {
    contents=<>
      {rounded([w,h*.85,d],[0,h*.43,0],'#eceee7',.12)}
      {rounded([w*.84,.025,d*.73],[0,h*.87,0],'#9cbbb9',.08)}
      {[-1,1].map(side=><group key={side}>{rounded([w,h*.13,d*.10],[0,h*.935,side*d*.45],'#fafaf6')}</group>)}
    </>
  } else if(model==='washer') {
    contents=<>{rounded([w,h,d],[0,h/2,0],'#e6e8e4')}
      <mesh position={[0,h*.47,d/2+.002]} rotation={[Math.PI/2,0,0]}><cylinderGeometry args={[w*.31,w*.31,.025,28]}/><meshStandardMaterial color="#333c42" metalness={.4} roughness={.3}/></mesh>
      {block([w*.84,h*.08,.012],[0,h*.88,d/2+.01],'#bfc7c7',false)}</>
  } else if(model==='fridge') {
    contents=<>{rounded([w,h,d],[0,h/2,0],'#c8cecc')}
      {block([w*.96,.012,.012],[0,h*.65,d/2+.01],accent,false)}
      {[.35,.8].map((y,i)=><group key={i}>{block([.025,h*.16,.035],[w*.34,h*y,d/2+.02],accent,false)}</group>)}
    </>
  } else if(model==='range') {
    contents=<>{block([w,h*.94,d],[0,h*.47,0],'#d9ddda',false)}
      {block([w*.8,h*.48,.012],[0,h*.38,d/2+.005],'#273037',false)}
      {block([w,.025,d],[0,h*.96,0],'#293237',false)}
      {[-1,1].flatMap(x=>[-1,1].map(z=><mesh key={`${x}${z}`} position={[x*w*.24,h*.98,z*d*.23]} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[w*.075,w*.12,16]}/><meshStandardMaterial color="#adb7b8" side={THREE.DoubleSide}/></mesh>))}
    </>
  } else if(model==='tv_console') {
    contents=<>
      {legs(.10,.07)}{block([w,h*.32,d],[0,h*.24,0],color)}
      {block([w*.18,.035,d*.32],[0,h*.415,0],accent,false)}
      {block([.04,h*.1,.04],[0,h*.46,0],accent,false)}
      {rounded([w*.74,h*.48,.045],[0,h*.75,0],'#25343b',.015)}
      {block([w*.68,h*.41,.004],[0,h*.75,.025],'#354b50',false)}
    </>
  } else {
    const tall=model==='wardrobe'
    contents=<>
      {legs(Math.min(.10,h*.12),.06)}{block([w,h*.88,d],[0,h*.54,0],color)}
      {block([w+.01,.035,d+.01],[0,h*.98,0],model==='island'||model==='vanity'?'#e8e5da':color,model!=='island'&&model!=='vanity')}
      {Array.from({length:tall?2:3},(_,i)=><group key={i}>
        {block(tall?[.008,h*.8,.008]:[w*.94,.008,.008],tall?[(i-.5)*w*.48,h*.54,d/2+.005]:[0,h*(.26+i*.23),d/2+.005],accent,false)}
        {block([.12,.012,.02],tall?[(i-.5)*w*.3,h*.52,d/2+.018]:[0,h*(.34+i*.23),d/2+.018],accent,false)}
      </group>)}
      {model==='vanity'&&<>{rounded([w*.66,.025,d*.65],[0,h*1.005,0],'#b5c7c3')}
        {block([.025,.14,.025],[0,h*1.07,-d*.33],accent,false)}</>}
    </>
  }
  return <group name={`furniture:${item.id}`} position={item.position} rotation={item.rotation} scale={item.scale}
    onClick={event=>{event.stopPropagation();const state=useProjectStore.getState();if(state.recording||state.viewMode==='walkthrough'||state.tourPointMode||state.placementMode)return;useProjectStore.setState({selectedFurnitureId:item.id,activePanel:'furniture',placementMode:false,tourPointMode:false})}}>
    <group position={[0,-h/2,0]}>{contents}</group>
    {selected&&<mesh position={[0,-h/2+.045,0]} rotation={[-Math.PI/2,0,0]}><planeGeometry args={[w+.10,d+.10]}/><meshBasicMaterial color="#17b9d3" transparent opacity={.25} depthWrite={false}/></mesh>}
  </group>
}
