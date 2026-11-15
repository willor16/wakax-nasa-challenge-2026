<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <CaptureSubnavBar />

    <ShellHudWindow
      class="flex-1"
      title="Capture · Auscultation Audio"
      subtitle="Verify ambient noise below 55 dBA and record 30-second anatomical sample"
      icon="mic"
      tag-text="HEART & LUNGS · 30S"
    >
      <p class="text-[12px] text-cabin-muted">
        30-second cardiac and pulmonary acoustic recorder slot (D2-06).
      </p>
    </ShellHudWindow>
  </div>
</template>
