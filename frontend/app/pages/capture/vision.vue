<template>
  <ShellHudWindow
    class="flex-1"
    title="Capture · Vision & Ocular"
    subtitle="Bilateral optic nerve sheath, intraocular pressure, and acuity log"
    icon="reticle"
    tag-text="DATA CAPTURE"
  >
    <div class="flex flex-wrap gap-2 mb-4">
      <NuxtLink to="/capture/auscultation" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Auscultation Audio
      </NuxtLink>
      <NuxtLink to="/capture/physical" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Physical & Labs
      </NuxtLink>
      <NuxtLink to="/capture/vision" class="px-4 h-9 rounded-[4px] menu-item-active text-[11.5px] font-bold flex items-center text-cabin-text">
        Vision & Ocular
      </NuxtLink>
      <NuxtLink to="/capture/psych-sleep" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Psych, Motor & Sleep
      </NuxtLink>
    </div>
    <p class="text-[12px] text-cabin-muted">
      Bilateral ocular capture form with 3.0 mm axial guide slot (D2-02).
    </p>
  </ShellHudWindow>
</template>
