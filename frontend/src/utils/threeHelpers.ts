import * as THREE from 'three'

export function createWallGeometry(start: THREE.Vector3, end: THREE.Vector3, height: number, thickness: number) {
  const direction = new THREE.Vector3().subVectors(end, start)
  const length = direction.length()
  const center = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5)
  const angle = Math.atan2(direction.x, direction.z)

  const geometry = new THREE.BoxGeometry(thickness, height, length)
  const matrix = new THREE.Matrix4()
  matrix.makeRotationY(angle)
  matrix.setPosition(center.x, height / 2, center.z)
  geometry.applyMatrix4(matrix)

  return geometry
}

export function hexToColor(hex: string): THREE.Color {
  return new THREE.Color(hex)
}
