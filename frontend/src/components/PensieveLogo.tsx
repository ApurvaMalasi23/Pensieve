"use client";

import React from "react";

interface PensieveLogoProps {
  size?: number | string;
  className?: string;
  strokeWidth?: number;
  color?: string; // default to Hermès Amber #E59500 or currentColor
  glow?: boolean;
}

/**
 * Pensieve Geometric Brand Mark (Sacred Geometry / Inscribed Circle & Bisector)
 * Designed with mathematical precision:
 * - Equilateral Triangle: Apex (100, 19), Left (7.63, 179), Right (192.37, 179)
 * - Inscribed Circle: Center (100, 125.67), Radius (53.33)
 * - Vertical Meridian: (100, 19) to (100, 179)
 */
export const PensieveLogo: React.FC<PensieveLogoProps> = ({
  size = 24,
  className = "",
  strokeWidth = 3,
  color = "#E59500",
  glow = false,
}) => {
  return (
    <svg
      viewBox="0 0 200 200"
      width={size}
      height={size}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`${glow ? "drop-shadow-[0_0_12px_rgba(229,149,0,0.4)]" : ""} ${className}`}
      aria-label="Pensieve Logo"
    >
      {/* Equilateral Triangle */}
      <polygon
        points="100,19 7.63,179 192.37,179"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* Inscribed Circle (touching base and sides) */}
      <circle
        cx="100"
        cy="125.67"
        r="53.33"
        stroke={color}
        strokeWidth={strokeWidth}
      />
      {/* Vertical Bisecting Meridian Line */}
      <line
        x1="100"
        y1="19"
        x2="100"
        y2="179"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
    </svg>
  );
};
