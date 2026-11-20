"use client";

import Footer from "@/components/site/Footer";
import Header from "@/components/site/Header";
import Motion from "@/components/site/Motion";
import { SiteProvider, useSite } from "@/lib/site";

function Frame({ children }: { children: React.ReactNode }) {
  const { ready } = useSite();
  return (
    <>
      <Header />
      <main id="main" style={{ minHeight: "60vh" }}>{ready ? children : null}</main>
      <Footer />
      <Motion />
    </>
  );
}

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <SiteProvider>
      <Frame>{children}</Frame>
    </SiteProvider>
  );
}
