<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-[18px] flex-1">
    <ShellHudWindow
      class="lg:col-span-12"
      title="Personal Biometric Profile"
      subtitle="Read-only baseline comparison across Launch, Mission, and Return"
      icon="vitruvian"
      tag-text="READ ONLY"
    >
      <div class="flex gap-2 mb-4">
        <NuxtLink to="/profile/personal" class="px-4 h-9 rounded-[4px] menu-item-active text-[11.5px] font-bold flex items-center text-cabin-text">
          Personal Data
        </NuxtLink>
        <NuxtLink to="/profile/psychological" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
          Psychological
        </NuxtLink>
        <NuxtLink to="/profile/physical" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
          Physical & Clinical
        </NuxtLink>
      </div>
      <p class="text-[12px] text-cabin-muted">
        Biometric hologram and longitudinal baseline comparison slot (D2-03).
      </p>
    </ShellHudWindow>
  </div>
</template>
