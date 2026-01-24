<script lang="ts">
	import { onMount } from 'svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';

	type BillingItem = {
		createdAt: string;
		userId?: string | null;
		userName?: string | null;
		userEmail?: string | null;
		provider?: string | null;
		model?: string | null;
		promptTokens?: number | null;
		completionTokens?: number | null;
		totalTokens?: number | null;
		costUsd?: number | null;
		latencyMs?: number | null;
	};

	let items: BillingItem[] = [];
	let loading = true;
	let error: string | null = null;
	let page = 1;
	const pageSize = 10;
	let isLastPage = false;

	// Filter state
	let dateFrom = '';
	let dateTo = '';
	let orderBy = '';
	let orderDir = '';

	const loadPage = async (targetPage: number) => {
		loading = true;
		error = null;

		const safePage = Math.max(1, targetPage);

		try {
			const params = new URLSearchParams();
			params.set('page', String(safePage));

			if (dateFrom.trim()) {
				params.set('date_from', dateFrom.trim());
			}
			if (dateTo.trim()) {
				params.set('date_to', dateTo.trim());
			}
			if (orderBy) {
				params.set('order_by', orderBy);
			}
			if (orderDir) {
				params.set('order_dir', orderDir);
			}

			const res = await fetch(`${WEBUI_BASE_URL}/api/billing?${params.toString()}`, {
				method: 'GET',
				headers: {
					Accept: 'application/json',
					'Content-Type': 'application/json',
					...(localStorage.token && { Authorization: `Bearer ${localStorage.token}` })
				}
			});

			if (!res.ok) {
				const body = await res.json().catch(() => ({}));
				const detail = body?.detail ?? res.statusText ?? 'Ошибка загрузки данных';
				throw new Error(typeof detail === 'string' ? detail : 'Ошибка загрузки данных');
			}

			const data = (await res.json()) as BillingItem[];
			items = Array.isArray(data) ? data : [];
			page = safePage;
			isLastPage = items.length < pageSize;
		} catch (e: unknown) {
			console.error(e);
			error = e instanceof Error ? e.message : 'Не удалось загрузить данные';
		} finally {
			loading = false;
		}
	};

	const applyFilters = () => {
		loadPage(1);
	};

	onMount(async () => {
		await loadPage(1);
	});

	function formatSpeed(latencyMs: number | null | undefined): string {
		if (latencyMs == null || latencyMs <= 0) return '—';
		const tokensPerSec = 1000 / latencyMs;
		return `${tokensPerSec.toFixed(2)} т/с`;
	}
</script>

<div class="px-4.5 w-full mx-auto max-w-7xl py-4 space-y-3">
	<!-- Filters Panel -->
	<div class="border border-gray-200 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-900 p-3">
		<div class="flex flex-wrap items-end gap-2">
			<!-- Date From -->
			<div class="flex-1 min-w-[140px]">
				<label class="block text-xs text-gray-600 dark:text-gray-400 mb-0.5">Дата от</label>
				<input
					type="datetime-local"
					class="w-full px-2 py-1 text-xs rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
					bind:value={dateFrom}
				/>
			</div>

			<!-- Date To -->
			<div class="flex-1 min-w-[140px]">
				<label class="block text-xs text-gray-600 dark:text-gray-400 mb-0.5">Дата до</label>
				<input
					type="datetime-local"
					class="w-full px-2 py-1 text-xs rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
					bind:value={dateTo}
				/>
			</div>

			<!-- Order By -->
			<div class="flex-1 min-w-[140px]">
				<label class="block text-xs text-gray-600 dark:text-gray-400 mb-0.5">Сортировка</label>
				<select
					class="w-full px-2 py-1 text-xs rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
					bind:value={orderBy}
				>
					<option value="">По умолчанию</option>
					<option value="prompt_tokens">Вх. токены</option>
					<option value="completion_tokens">Вых. токены</option>
					<option value="cost_usd">Стоимость</option>
					<option value="latency_ms">Скорость</option>
				</select>
			</div>

			<!-- Order Direction -->
			<div class="flex-1 min-w-[120px]">
				<label class="block text-xs text-gray-600 dark:text-gray-400 mb-0.5">Порядок</label>
				<select
					class="w-full px-2 py-1 text-xs rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
					bind:value={orderDir}
				>
					<option value="desc">Убывание</option>
					<option value="asc">Возрастание</option>
				</select>
			</div>

			<!-- Apply Button -->
			<button
				class="px-3 py-1 text-xs font-medium rounded border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-default"
				on:click={applyFilters}
				disabled={loading}
			>
				Применить
			</button>
		</div>
	</div>

	{#if error}
		<div class="text-sm text-red-600 dark:text-red-400">
			{error}
		</div>
	{/if}

	{#if loading}
		<div class="text-sm text-gray-400 dark:text-gray-600">Загрузка…</div>
	{:else if items.length === 0 && !error}
		<div class="text-sm text-gray-400 dark:text-gray-600">Нет данных для отображения.</div>
	{:else}
		<div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-2">
			<div>Страница {page}</div>
			<div class="inline-flex gap-2">
				<button
					class="px-2 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 disabled:cursor-default hover:bg-gray-50 dark:hover:bg-gray-800"
					on:click={() => loadPage(page - 1)}
					disabled={page <= 1 || loading}
				>
					Назад
				</button>
				<button
					class="px-2 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 disabled:cursor-default hover:bg-gray-50 dark:hover:bg-gray-800"
					on:click={() => loadPage(page + 1)}
					disabled={isLastPage || loading}
				>
					Вперёд
				</button>
			</div>
		</div>

		<div class="overflow-x-auto border border-gray-200 dark:border-gray-800 rounded-xl bg-white dark:bg-gray-900 shadow-sm">
			<table class="w-full text-sm text-left">
				<thead class="text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
					<tr>
						<th class="px-4 py-3 whitespace-nowrap">Время создания</th>
						<th class="px-4 py-3 whitespace-nowrap">Пользователь</th>
						<th class="px-4 py-3 whitespace-nowrap">Модель</th>
						<th class="px-4 py-3 whitespace-nowrap text-right">Вх. токены</th>
						<th class="px-4 py-3 whitespace-nowrap text-right">Вых. токены</th>
						<th class="px-4 py-3 whitespace-nowrap text-right">Всего токенов</th>
						<th class="px-4 py-3 whitespace-nowrap text-right">Стоимость $</th>
						<th class="px-4 py-3 whitespace-nowrap text-right">Скорость</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-100 dark:divide-gray-800">
					{#each items as item}
						<tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50">
							<td class="px-4 py-3 text-gray-700 dark:text-gray-300 whitespace-nowrap">
								{item.createdAt || '—'}
							</td>
							<td class="px-4 py-3 text-gray-700 dark:text-gray-300">
								{#if item.userName || item.userEmail}
									<div class="max-w-xs">
										<div class="font-medium">{item.userName ?? '—'}</div>
										{#if item.userEmail}
											<div class="text-xs text-gray-500 dark:text-gray-400">
												({item.userEmail})
											</div>
										{/if}
									</div>
								{:else}
									<span class="text-gray-400 dark:text-gray-500">—</span>
								{/if}
							</td>
							<td class="px-4 py-3 text-gray-700 dark:text-gray-300">
								<div class="max-w-sm">
									{#if item.provider}
										<span class="text-xs text-gray-500 dark:text-gray-400">{item.provider}/</span>
									{/if}
									<span class="break-words">{item.model ?? '—'}</span>
								</div>
							</td>
							<td class="px-4 py-3 text-gray-700 dark:text-gray-300 text-right tabular-nums">
								{item.promptTokens ?? '—'}
							</td>
							<td class="px-4 py-3 text-gray-700 dark:text-gray-300 text-right tabular-nums">
								{item.completionTokens ?? '—'}
							</td>
							<td class="px-4 py-3 text-gray-700 dark:text-gray-300 text-right tabular-nums">
								{item.totalTokens ?? '—'}
							</td>
							<td class="px-4 py-3 text-gray-700 dark:text-gray-300 text-right tabular-nums">
								{item.costUsd != null ? item.costUsd.toFixed(6) : '—'}
							</td>
							<td class="px-4 py-3 text-gray-700 dark:text-gray-300 text-right whitespace-nowrap">
								{formatSpeed(item.latencyMs)}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 pt-2">
			<div>Страница {page}</div>
			<div class="inline-flex gap-2">
				<button
					class="px-2 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 disabled:cursor-default hover:bg-gray-50 dark:hover:bg-gray-800"
					on:click={() => loadPage(page - 1)}
					disabled={page <= 1 || loading}
				>
					Назад
				</button>
				<button
					class="px-2 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 disabled:cursor-default hover:bg-gray-50 dark:hover:bg-gray-800"
					on:click={() => loadPage(page + 1)}
					disabled={isLastPage || loading}
				>
					Вперёд
				</button>
			</div>
		</div>
	{/if}
</div>

