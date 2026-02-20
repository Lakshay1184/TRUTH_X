"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Sphere, MeshDistortMaterial, Float, Environment, OrbitControls } from "@react-three/drei";
import { useRef, useState } from "react";
import * as THREE from "three";

function Agent({ position, color, speed, delay, scale }: { position: [number, number, number], color: string, speed: number, delay: number, scale: number }) {
    const meshRef = useRef<THREE.Mesh>(null!);
    const [hovered, setHovered] = useState(false);
    const [active, setActive] = useState(false);

    useFrame((state) => {
        const t = state.clock.getElapsedTime();

        // Look at mouse
        if (meshRef.current) {
            const mouseX = (state.mouse.x * window.innerWidth) / 2;
            const mouseY = (state.mouse.y * window.innerHeight) / 2;
            meshRef.current.rotation.x = THREE.MathUtils.lerp(meshRef.current.rotation.x, mouseY * 0.0005, 0.1);
            meshRef.current.rotation.y = THREE.MathUtils.lerp(meshRef.current.rotation.y, mouseX * 0.0005, 0.1);
        }
    });

    return (
        <Float
            speed={speed}
            rotationIntensity={1}
            floatIntensity={2}
            floatingRange={[-0.2, 0.2]}
        >
            <mesh
                ref={meshRef}
                position={position}
                scale={active ? scale * 1.2 : hovered ? scale * 1.1 : scale}
                onClick={() => setActive(!active)}
                onPointerOver={() => setHovered(true)}
                onPointerOut={() => setHovered(false)}
            >
                <sphereGeometry args={[1, 64, 64]} />
                <MeshDistortMaterial
                    color={active ? "#ff0055" : hovered ? "#00ffff" : color}
                    envMapIntensity={1}
                    clearcoat={1}
                    clearcoatRoughness={0}
                    metalness={0.9}
                    roughness={0.1}
                    distort={0.4}
                    speed={2}
                />
                {/* Glow Core / Eye */}
                <mesh position={[0, 0, 0.8]} scale={0.2}>
                    <sphereGeometry args={[1, 32, 32]} />
                    <meshStandardMaterial
                        color={active ? "#ff0000" : "#00ffff"}
                        emissive={active ? "#ff0000" : "#00ffff"}
                        emissiveIntensity={2}
                        toneMapped={false}
                    />
                </mesh>
            </mesh>
        </Float>
    );
}

export default function AgentScene() {
    return (
        <div className="fixed inset-0 z-0 pointer-events-none"> {/* z-0 ensures it is behind content but visible */}
            <Canvas className="pointer-events-auto" camera={{ position: [0, 0, 8], fov: 45 }}>
                {/* Lighting */}
                <ambientLight intensity={0.5} />
                <pointLight position={[10, 10, 10]} intensity={1.5} color="#00d4ff" />
                <pointLight position={[-10, -10, -10]} intensity={1} color="#a855f7" />

                {/* Agents */}
                <group position={[0, -0.5, 0]}>
                    <Agent position={[-2.5, 0.5, 0]} color="#4B0082" speed={1.5} delay={0} scale={1.2} />
                    <Agent position={[0, 0, 1]} color="#000000" speed={2} delay={1} scale={1.5} />
                    <Agent position={[2.5, -0.5, -1]} color="#2E0249" speed={1.2} delay={2} scale={1.1} />
                </group>

                <Environment preset="city" />
                <OrbitControls enableZoom={false} enablePan={false} autoRotate={true} autoRotateSpeed={0.5} />
            </Canvas>
        </div>
    );
}
