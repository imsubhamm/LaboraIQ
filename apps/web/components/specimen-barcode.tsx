"use client";

import { useEffect, useRef } from "react";
import JsBarcode from "jsbarcode";

type SpecimenBarcodeProps = {
  value: string;
};

export function SpecimenBarcode({ value }: SpecimenBarcodeProps) {
  const barcodeRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!barcodeRef.current) return;
    JsBarcode(barcodeRef.current, value, {
      format: "CODE128",
      displayValue: false,
      width: 2,
      height: 58,
      margin: 10,
      background: "#ffffff",
      lineColor: "#101817",
    });
  }, [value]);

  return (
    <svg
      ref={barcodeRef}
      className="barcode-bars"
      role="img"
      aria-label={`Code 128 specimen barcode ${value}`}
      data-barcode-value={value}
    />
  );
}
