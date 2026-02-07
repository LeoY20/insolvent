import React from 'react';

type SummaryCardProps = {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  colorClass: string;
};

export function SummaryCard({ title, value, icon, colorClass }: SummaryCardProps) {
  return (
    <div className={`p-4 rounded-lg shadow-md flex items-center ${colorClass}`}>
      <div className="p-3 rounded-full bg-white bg-opacity-30">
        {icon}
      </div>
      <div className="ml-4">
        <p className="text-sm font-medium text-white opacity-90">{title}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
      </div>
    </div>
  );
}
