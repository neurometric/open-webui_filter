<script lang="ts">
  import { onMount } from 'svelte';
  import { WEBUI_BASE_URL } from '$lib/constants';
  import GroupQuotaEditModal from './GroupQuotaEditModal.svelte';

  type QuotaMode = 'shared_evenly' | 'unique';

  type QuotaSummary = {
    totalBudgetUsd?: number | null;
    spentUsd?: number | null;
    remainingUsd?: number | null;
    spentPercent?: number | null;
  };

  type QuotaMonitoringItem = {
    scopeType: 'company' | 'group';
    scopeId: string;
    scopeName: string;
    budgetUsd?: number | null;
    spentUsd?: number | null;
    remainingUsd?: number | null;
    spentPercent?: number | null;
    warningPercent?: number | null;
    isActive: boolean;
    status: 'ok' | 'warning' | 'exceeded' | 'disabled' | 'no_quota';
    quotaMode?: QuotaMode;
  };

  type GroupOption = {
    id: string;
    name: string;
  };

  type GroupQuotaPayload = {
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

  
  let loading = true;
  let error: string | null = null;

  // summary
  let totalBudgetUsd: number | null = null;
  let spentUsd: number | null = null;
  let remainingUsd: number | null = null;
  let spentPercent: number | null = null;

  // filters
  let dateFrom = '';
  let dateTo = '';
  let selectedGroupIds: string[] = [];

  // groups options
  let groupOptions: GroupOption[] = [];
  let groupsLoading = false;

  // dropdown state
  let groupDropdownOpen = false;
  let groupSearch = '';
  let groupBoxEl: HTMLDivElement | null = null;

  // monitoring data
  let items: QuotaMonitoringItem[] = [];

  // client-side pagination
  let page = 1;
  const pageSize = 10;

  // edit modal
  let editModalOpen = false;
  let editLoading = false;
  let selectedGroupQuota: QuotaMonitoringItem | null = null;

  let usersQuota: GroupUserQuotaItem[] = [];
  let usersQuotaLoading = false;

  function authHeaders() {
    return {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(localStorage.token && { Authorization: `Bearer ${localStorage.token}` })
    };
  }

  function containsCI(haystack: string, needle: string) {
    return haystack.toLowerCase().includes(needle.toLowerCase());
  }

  function toggleGroup(id: string) {
    if (selectedGroupIds.includes(id)) {
      selectedGroupIds = selectedGroupIds.filter((x) => x !== id);
    } else {
      selectedGroupIds = [...selectedGroupIds, id];
    }
  }

  function removeGroup(id: string) {
    selectedGroupIds = selectedGroupIds.filter((x) => x !== id);
  }

  function clearGroups() {
    selectedGroupIds = [];
  }

  function getGroupName(id: string): string {
    return groupOptions.find((g) => g.id === id)?.name ?? id;
  }

  function statusLabel(status: QuotaMonitoringItem['status']) {
    if (status === 'ok') return 'OK';
    if (status === 'warning') return 'Warning';
    if (status === 'exceeded') return 'Exceeded';
    if (status === 'disabled') return 'Disabled';
    if (status === 'no_quota') return 'Нет квоты';
    return status;
  }

  function statusClass(status: QuotaMonitoringItem['status']) {
    if (status === 'ok') {
      return 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950/30 dark:text-green-400 dark:border-green-900';
    }
    if (status === 'warning') {
      return 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950/30 dark:text-yellow-400 dark:border-yellow-900';
    }
    if (status === 'exceeded') {
      return 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/30 dark:text-red-400 dark:border-red-900';
    }
    if (status === 'disabled') {
      return 'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700';
    }
    if (status === 'no_quota') {
      return 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900/40 dark:text-slate-300 dark:border-slate-700';
    }
    return 'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700';
  }

  async function loadGroups() {
    groupsLoading = true;
    try {
      const params = new URLSearchParams();

      if (dateFrom.trim()) params.set('date_from', dateFrom.trim());
      if (dateTo.trim()) params.set('date_to', dateTo.trim());

      const res = await fetch(`${WEBUI_BASE_URL}/api/quotas/monitoring?${params.toString()}`, {
        method: 'GET',
        headers: authHeaders()
      });

      if (!res.ok) throw new Error('Не удалось загрузить список групп');

      const data = (await res.json()) as QuotaMonitoringItem[];
      const groups = (Array.isArray(data) ? data : [])
        .filter((x) => x.scopeType === 'group')
        .map((x) => ({ id: x.scopeId, name: x.scopeName }));

      const unique = new Map<string, GroupOption>();
      for (const g of groups) unique.set(g.id, g);

      groupOptions = Array.from(unique.values()).sort((a, b) => a.name.localeCompare(b.name));
    } catch (e) {
      console.error(e);
      groupOptions = [];
    } finally {
      groupsLoading = false;
    }
  }

  async function loadSummary() {
    try {
      const params = new URLSearchParams();

      if (dateFrom.trim()) params.set('date_from', dateFrom.trim());
      if (dateTo.trim()) params.set('date_to', dateTo.trim());

      const res = await fetch(`${WEBUI_BASE_URL}/api/quotas/summary?${params.toString()}`, {
        method: 'GET',
        headers: authHeaders()
      });

      if (!res.ok) {
        totalBudgetUsd = null;
        spentUsd = null;
        remainingUsd = null;
        spentPercent = null;
        return;
      }

      const data = (await res.json()) as QuotaSummary;
      totalBudgetUsd = typeof data?.totalBudgetUsd === 'number' ? data.totalBudgetUsd : null;
      spentUsd = typeof data?.spentUsd === 'number' ? data.spentUsd : null;
      remainingUsd = typeof data?.remainingUsd === 'number' ? data.remainingUsd : null;
      spentPercent = typeof data?.spentPercent === 'number' ? data.spentPercent : null;
    } catch (e) {
      console.error(e);
      totalBudgetUsd = null;
      spentUsd = null;
      remainingUsd = null;
      spentPercent = null;
    }
  }

  async function loadMonitoring() {
    try {
      const params = new URLSearchParams();

      if (dateFrom.trim()) params.set('date_from', dateFrom.trim());
      if (dateTo.trim()) params.set('date_to', dateTo.trim());

      for (const groupId of selectedGroupIds) {
        params.append('group_ids', groupId);
      }

      const res = await fetch(`${WEBUI_BASE_URL}/api/quotas/monitoring?${params.toString()}`, {
        method: 'GET',
        headers: authHeaders()
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail = body?.detail ?? res.statusText ?? 'Ошибка загрузки мониторинга';
        throw new Error(typeof detail === 'string' ? detail : 'Ошибка загрузки мониторинга');
      }

      const data = (await res.json()) as QuotaMonitoringItem[];
      items = Array.isArray(data) ? data : [];
      page = 1;
    } catch (e) {
      console.error(e);
      throw e;
    }
  }

  async function loadAll() {
    loading = true;
    error = null;

    try {
      await Promise.all([loadSummary(), loadMonitoring()]);
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Не удалось загрузить данные';
    } finally {
      loading = false;
    }
  }

  async function applyFilters() {
    await loadAll();
  }

  function paginatedItems() {
    const start = (page - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }

  function totalPages() {
    return Math.max(1, Math.ceil(items.length / pageSize));
  }

  function nextPage() {
    if (page < totalPages()) page += 1;
  }

  function prevPage() {
    if (page > 1) page -= 1;
  }

  async function openEditQuota(quota: QuotaMonitoringItem) {
    if (quota.scopeType !== 'group') return;

    selectedGroupQuota = quota;
    usersQuota = [];
    editModalOpen = true;

    await loadGroupUsersQuota(quota.scopeId);
  }

  function closeEditModal() {
    editModalOpen = false;
    selectedGroupQuota = null;
    usersQuota = [];
    usersQuotaLoading = false;
  }

  async function saveGroupQuota(event: CustomEvent<GroupQuotaPayload>) {
    const payload = event.detail;
    editLoading = true;

    try {
      const res = await fetch(`${WEBUI_BASE_URL}/api/quotas/groups/${payload.scopeId}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          budgetUsd: payload.budgetUsd,
          isActive: payload.isActive,
          quotaMode: payload.quotaMode
        })
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail = body?.detail ?? 'Не удалось сохранить квоту';
        throw new Error(typeof detail === 'string' ? detail : 'Не удалось сохранить квоту');
      }

      const updated = (await res.json()) as QuotaMonitoringItem;

      items = items.map((item) =>
        item.scopeType === 'group' && item.scopeId === updated.scopeId
          ? { ...item, ...updated }
          : item
      );

      if (selectedGroupQuota?.scopeId === updated.scopeId) {
        selectedGroupQuota = { ...selectedGroupQuota, ...updated };
      }

      await loadSummary();
      closeEditModal();
    } catch (e) {
      console.error(e);
      error = e instanceof Error ? e.message : 'Ошибка сохранения квоты';
    } finally {
      editLoading = false;
    }
  }

  onMount(() => {
    const onDocClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (groupBoxEl && !groupBoxEl.contains(t)) groupDropdownOpen = false;
    };

    document.addEventListener('click', onDocClick, true);

    void (async () => {
      await loadGroups();
      await loadAll();
    })();

    return () => {
      document.removeEventListener('click', onDocClick, true);
    };
  });

  async function loadGroupUsersQuota(groupId: string) {
  usersQuotaLoading = true;

  try {
    const res = await fetch(`${WEBUI_BASE_URL}/api/quotas/groups/${groupId}/users`, {
      method: 'GET',
      headers: authHeaders()
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = body?.detail ?? 'Не удалось загрузить пользователей группы';
      throw new Error(typeof detail === 'string' ? detail : 'Не удалось загрузить пользователей группы');
    }

    const data = (await res.json()) as GroupUserQuotaItem[];
    usersQuota = Array.isArray(data) ? data : [];
  } catch (e) {
    console.error(e);
    usersQuota = [];
  } finally {
    usersQuotaLoading = false;
  }
}
</script>

<div class="px-4.5 w-full mx-auto max-w-7xl py-4 space-y-3">
  <div class="border border-gray-200 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-900 p-3">
    <div class="flex flex-wrap items-end gap-2">
      <div class="flex-1 min-w-[160px]">
        <label class="block text-xs text-gray-600 dark:text-gray-400 mb-0.5">Дата от</label>
        <input
          type="datetime-local"
          class="w-full px-2 py-1 text-xs rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          bind:value={dateFrom}
        />
      </div>

      <div class="flex-1 min-w-[160px]">
        <label class="block text-xs text-gray-600 dark:text-gray-400 mb-0.5">Дата до</label>
        <input
          type="datetime-local"
          class="w-full px-2 py-1 text-xs rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          bind:value={dateTo}
        />
      </div>

      <div class="flex-[2] min-w-[260px] relative" bind:this={groupBoxEl}>
        <label class="block text-xs text-gray-600 dark:text-gray-400 mb-0.5">Группы</label>
        <div
          class="w-full h-[28px] px-2 py-1 text-xs rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 outline-none focus-within:ring-1 focus-within:ring-blue-500 focus-within:border-blue-500 cursor-text flex items-center gap-2 overflow-hidden"
          on:click|stopPropagation={() => (groupDropdownOpen = !groupDropdownOpen)}
          role="button"
          tabindex="0"
        >
          <div class="flex-1 overflow-x-auto hscroll-no-bar">
            <div class="flex items-center gap-1 whitespace-nowrap pr-1">
              {#each selectedGroupIds as groupId}
                <span
                  class="shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800"
                >
                  <span class="max-w-[160px] truncate">{getGroupName(groupId)}</span>
                  <button
                    class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    on:click|stopPropagation={() => removeGroup(groupId)}
                    aria-label="Удалить"
                    title="Удалить"
                    type="button"
                  >
                    ✕
                  </button>
                </span>
              {/each}

              {#if selectedGroupIds.length === 0}
                <span class="text-gray-400 dark:text-gray-500">Выберите группы</span>
              {/if}
            </div>
          </div>

          <div class="shrink-0 inline-flex items-center gap-1 self-center">
            {#if selectedGroupIds.length > 0}
              <button
                class="h-[20px] w-[24px] inline-flex items-center justify-center rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                on:click|stopPropagation={clearGroups}
                aria-label="Очистить всё"
                title="Очистить всё"
                type="button"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            {/if}

            <button
              class="h-[20px] w-[24px] ml-auto inline-flex items-center justify-center rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
              on:click|stopPropagation={() => (groupDropdownOpen = true)}
              aria-label="Поиск"
              title="Поиск"
              type="button"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M21 21l-4.35-4.35m1.85-5.15a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
          </div>
        </div>

        {#if groupDropdownOpen}
          <div
            class="absolute left-0 top-full mt-1 w-full z-50 border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-900 shadow-sm overflow-hidden"
            on:click|stopPropagation
          >
            <div class="p-2 border-b border-gray-200 dark:border-gray-700">
              <input
                class="w-full px-2 py-1 text-xs rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Поиск…"
                bind:value={groupSearch}
                on:click|stopPropagation
              />
            </div>

            <div class="max-h-[300px] overflow-auto">
              {#if groupsLoading}
                <div class="p-2 text-xs text-gray-400 dark:text-gray-600">Загрузка…</div>
              {:else}
                {#each groupOptions.filter((g) => !groupSearch.trim() || containsCI(g.name, groupSearch.trim())) as g}
                  <button
                    class="w-full text-left px-2 py-1.5 text-xs hover:bg-gray-50 dark:hover:bg-gray-800 flex items-center gap-2"
                    on:click={() => toggleGroup(g.id)}
                    type="button"
                  >
                    <span class="inline-block w-4 text-center">
                      {#if selectedGroupIds.includes(g.id)}✓{:else}&nbsp;{/if}
                    </span>
                    <span class="truncate">{g.name}</span>
                  </button>
                {:else}
                  <div class="p-2 text-xs text-gray-400 dark:text-gray-600">Нет совпадений</div>
                {/each}
              {/if}
            </div>
          </div>
        {/if}
      </div>

      <button
        class="px-3 py-1 text-xs font-medium rounded border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-default"
        on:click={applyFilters}
        disabled={loading || groupsLoading}
      >
        Применить
      </button>
    </div>
  </div>

  {#if error}
    <div class="text-sm text-red-600 dark:text-red-400">{error}</div>
  {/if}

  <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
    <div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 shadow-sm">
      <div class="text-xs text-gray-500 dark:text-gray-400">Общий бюджет</div>
      <div class="mt-1 text-lg font-semibold text-gray-800 dark:text-gray-100 tabular-nums">
        {#if totalBudgetUsd == null}—{:else}${totalBudgetUsd.toFixed(2)}{/if}
      </div>
    </div>

    <div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 shadow-sm">
      <div class="text-xs text-gray-500 dark:text-gray-400">Израсходовано</div>
      <div class="mt-1 text-lg font-semibold text-gray-800 dark:text-gray-100 tabular-nums">
        {#if spentUsd == null}
          —
        {:else}
          ${spentUsd.toFixed(6)}
          {#if spentPercent != null}
            <span class="ml-1 text-xs font-medium text-gray-500 dark:text-gray-400">
              ({spentPercent.toFixed(2)}%)
            </span>
          {/if}
        {/if}
      </div>
    </div>

    <div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 shadow-sm">
      <div class="text-xs text-gray-500 dark:text-gray-400">Остаток</div>
      <div class="mt-1 text-lg font-semibold text-gray-800 dark:text-gray-100 tabular-nums">
        {#if remainingUsd == null}—{:else}${remainingUsd.toFixed(6)}{/if}
      </div>
    </div>
  </div>

  {#if loading}
    <div class="text-sm text-gray-400 dark:text-gray-600">Загрузка…</div>
  {:else if items.length === 0 && !error}
    <div class="text-sm text-gray-400 dark:text-gray-600">Нет данных для отображения.</div>
  {:else}
    <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-2">
      <div>Страница {page} / {totalPages()}</div>
      <div>Всего записей: {items.length}</div>
    </div>

    <div class="overflow-x-auto border border-gray-200 dark:border-gray-800 rounded-xl bg-white dark:bg-gray-900 shadow-sm">
      <table class="w-full text-sm text-left">
        <thead class="text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
          <tr>
            <th class="px-4 py-3 whitespace-nowrap">Тип</th>
            <th class="px-4 py-3 whitespace-nowrap">Название</th>
            <th class="px-4 py-3 whitespace-nowrap text-right">Бюджет $</th>
            <th class="px-4 py-3 whitespace-nowrap text-right">Израсходовано $</th>
            <th class="px-4 py-3 whitespace-nowrap text-right">Остаток $</th>
            <th class="px-4 py-3 whitespace-nowrap text-right">Использование %</th>
            <th class="px-4 py-3 whitespace-nowrap text-center">Статус</th>
            <th class="px-4 py-3 whitespace-nowrap text-center">Действия</th>
          </tr>
        </thead>

        <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
          {#each paginatedItems() as item}
            <tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50">
              <td class="px-4 py-3 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                <span class="capitalize">{item.scopeType}</span>
              </td>

              <td class="px-4 py-3 text-gray-700 dark:text-gray-300">
                <div class="max-w-sm break-words">{item.scopeName}</div>
              </td>

              <td class="px-4 py-3 text-gray-700 dark:text-gray-300 text-right tabular-nums">
                {#if item.budgetUsd == null}—{:else}{item.budgetUsd.toFixed(2)}{/if}
              </td>

              <td class="px-4 py-3 text-gray-700 dark:text-gray-300 text-right tabular-nums">
                {#if item.spentUsd == null}—{:else}{item.spentUsd.toFixed(6)}{/if}
              </td>

              <td class="px-4 py-3 text-gray-700 dark:text-gray-300 text-right tabular-nums">
                {#if item.remainingUsd == null}—{:else}{item.remainingUsd.toFixed(6)}{/if}
              </td>

              <td class="px-4 py-3 text-gray-700 dark:text-gray-300 text-right tabular-nums">
                {#if item.spentPercent == null}—{:else}{item.spentPercent.toFixed(2)}%{/if}
              </td>

              <td class="px-4 py-3 text-center">
                <span class={`inline-flex items-center px-2 py-1 rounded-md border text-xs font-medium ${statusClass(item.status)}`}>
                  {statusLabel(item.status)}
                </span>
              </td>

              <td class="px-4 py-3 text-center">
                {#if item.scopeType === 'group'}
                  <button
                    class="px-2 py-1 rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-xs"
                    on:click={() => openEditQuota(item)}
                    type="button"
                  >
                    Редактировать
                  </button>
                {:else}
                  <span class="text-gray-400 dark:text-gray-600">—</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 pt-2">
      <div>Страница {page} / {totalPages()}</div>
      <div class="inline-flex gap-2">
        <button
          class="px-2 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 disabled:cursor-default hover:bg-gray-50 dark:hover:bg-gray-800"
          on:click={prevPage}
          disabled={page <= 1 || loading}
        >
          Назад
        </button>
        <button
          class="px-2 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 disabled:cursor-default hover:bg-gray-50 dark:hover:bg-gray-800"
          on:click={nextPage}
          disabled={page >= totalPages() || loading}
        >
          Вперёд
        </button>
      </div>
    </div>
  {/if}
</div>

<GroupQuotaEditModal
  open={editModalOpen}
  quota={selectedGroupQuota}
  loading={editLoading}
  usersQuota={usersQuota}
  usersQuotaLoading={usersQuotaLoading}
  on:close={closeEditModal}
  on:save={saveGroupQuota}
/>

<style>
  .hscroll-no-bar {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }

  .hscroll-no-bar::-webkit-scrollbar {
    height: 0;
  }
</style>