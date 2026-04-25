<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  type QuotaMode = 'shared_evenly' | 'unique';

  type GroupQuotaItem = {
    scopeId: string;
    scopeName: string;
    budgetUsd?: number | null;
    isActive: boolean;
    quotaMode?: QuotaMode;
  };

  type SavePayload = {
    scopeId: string;
    budgetUsd: number | null;
    isActive: boolean;
    quotaMode: QuotaMode;
  };

  type GroupUserQuotaItem = {
    userId: string;
    name: string;
    email?: string | null;
    allocatedUsd?: number | null;
    spentUsd: number;
  };

  export let open = false;
  export let quota: GroupQuotaItem | null = null;
  export let loading = false;

  export let usersQuota: GroupUserQuotaItem[] = [];
  export let usersQuotaLoading = false;

  const dispatch = createEventDispatcher<{
    close: void;
    save: SavePayload;
  }>();

  let usersExpanded = false;

  let form: {
    quotaMode: QuotaMode;
    budgetUsd: number | null;
    isActive: boolean;
  } = {
    quotaMode: 'shared_evenly',
    budgetUsd: null,
    isActive: true
  };

  $: if (open) {
    usersExpanded = false;
  }

  $: if (open && quota) {
    form = {
      quotaMode: quota.quotaMode ?? 'shared_evenly',
      budgetUsd: quota.budgetUsd ?? null,
      isActive: quota.isActive ?? true
    };
  }

  function close() {
    if (loading) return;
    dispatch('close');
  }

  function submit() {
    if (!quota) return;

    const normalizedBudget =
      form.budgetUsd === null || form.budgetUsd === undefined ? null : Number(form.budgetUsd);

    if (normalizedBudget != null && (!Number.isFinite(normalizedBudget) || normalizedBudget < 0)) {
      alert('Введите корректную сумму');
      return;
    }

    dispatch('save', {
      scopeId: quota.scopeId,
      budgetUsd: normalizedBudget,
      isActive: form.isActive,
      quotaMode: form.quotaMode
    });
  }

  function onBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      close();
    }
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      close();
    }
  }
</script>

<svelte:window on:keydown={onKeydown} />

{#if open && quota}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    on:click={onBackdropClick}
    role="presentation"
  >
    <div
      class="w-full max-w-lg rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="group-quota-modal-title"
    >
      <div
        class="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-800"
      >
        <div>
          <h2
            id="group-quota-modal-title"
            class="text-lg font-semibold text-gray-900 dark:text-white"
          >
            Редактирование квоты группы
          </h2>
          <div class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {quota.scopeName}
          </div>
        </div>

        <button
          class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700 text-gray-500 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800 disabled:opacity-50"
          on:click={close}
          disabled={loading}
          aria-label="Закрыть"
          type="button"
        >
          ✕
        </button>
      </div>

      <div class="px-5 py-4 space-y-4">
        <div>
          <label
            for="quota-mode"
            class="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            Вид квотирования
          </label>

          <select
            id="quota-mode"
            bind:value={form.quotaMode}
            class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          >
            <option value="shared_evenly">Равномерно на всех пользователей</option>
            <option value="unique">Уникальная квота группы</option>
          </select>

          {#if form.quotaMode === 'shared_evenly'}
            <p class="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
              Общий бюджет группы будет делиться поровну между всеми пользователями группы.
            </p>

            <div
              class="mt-3 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
            >
              <button
                type="button"
                class="flex w-full items-center justify-between px-3 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50"
                on:click={() => (usersExpanded = !usersExpanded)}
                disabled={loading}
              >
                <div>
                  <div class="text-sm font-medium text-gray-800 dark:text-gray-200">
                    Пользователи группы
                  </div>
                  <div class="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                    Сначала показываются пользователи с наибольшими расходами
                  </div>
                </div>

                <span class="text-sm text-gray-500 dark:text-gray-400">
                  {#if usersExpanded}▲{:else}▼{/if}
                </span>
              </button>

              {#if usersExpanded}
                <div class="border-t border-gray-200 dark:border-gray-700 px-3 py-3">
                  {#if usersQuotaLoading}
                    <div class="text-sm text-gray-500 dark:text-gray-400">Загрузка…</div>
                  {:else if usersQuota.length === 0}
                    <div class="text-sm text-gray-500 dark:text-gray-400">Нет пользователей</div>
                  {:else}
                    <div class="space-y-2">
                      <div
                        class="grid grid-cols-[1fr_90px_110px] px-3 text-xs text-gray-500 dark:text-gray-400"
                      >
                        <div>Пользователь</div>
                        <div class="text-right">Выделено</div>
                        <div class="text-right">Потрачено</div>
                      </div>

                      {#each usersQuota as userItem}
                        <div
                          class="grid grid-cols-[1fr_90px_110px] items-center rounded-md bg-gray-50 dark:bg-gray-800/50 px-3 py-2 text-sm"
                        >
                          <div class="pr-3 min-w-0">
                            <div class="font-medium text-gray-800 dark:text-gray-200 break-words">
                              {userItem.name}
                            </div>
                            {#if userItem.email}
                              <div class="text-xs text-gray-500 dark:text-gray-400 break-all">
                                {userItem.email}
                              </div>
                            {/if}
                          </div>

                          <div class="text-right tabular-nums text-gray-700 dark:text-gray-300">
                            {#if userItem.allocatedUsd != null}
                              {userItem.allocatedUsd.toFixed(2)}
                            {:else}
                              —
                            {/if}
                          </div>

                          <div class="text-right tabular-nums text-gray-700 dark:text-gray-300">
                            {userItem.spentUsd.toFixed(6)}
                          </div>
                        </div>
                      {/each}
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {:else}
            <p class="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
              Для группы будет использоваться единый общий лимит.
            </p>
          {/if}
        </div>

        <div>
          <label
            for="budget-usd"
            class="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            Сколько выделяем денег, USD
          </label>

          <input
            id="budget-usd"
            bind:value={form.budgetUsd}
            type="number"
            min="0"
            step="0.01"
            placeholder="Например, 25"
            class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />

          <p class="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
            Оставь пустым, если лимит не задан.
          </p>
        </div>

        <div class="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-3">
          <div class="flex items-center justify-between gap-4">
            <div>
              <div class="text-sm font-medium text-gray-800 dark:text-gray-200">
                Квота активна
              </div>
              <div class="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                При выключении ограничение для группы не применяется.
              </div>
            </div>

            <button
              type="button"
              class={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                form.isActive ? 'bg-green-600' : 'bg-gray-300 dark:bg-gray-700'
              }`}
              on:click={() => (form.isActive = !form.isActive)}
              disabled={loading}
              aria-pressed={form.isActive}
              aria-label="Переключить активность квоты"
            >
              <span
                class={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                  form.isActive ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      <div
        class="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-200 dark:border-gray-800"
      >
        <button
          class="rounded-lg border border-gray-300 dark:border-gray-700 px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
          on:click={close}
          disabled={loading}
          type="button"
        >
          Отмена
        </button>

        <button
          class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          on:click={submit}
          disabled={loading || !quota}
          type="button"
        >
          {#if loading}
            Сохранение...
          {:else}
            Сохранить
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}