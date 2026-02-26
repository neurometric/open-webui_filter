<script lang="ts">
	import { onMount } from 'svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';

	type RequestItem = {
		time: string;
		chatLink: string;
		originalText: string;
		modifiedText: string;
		userId?: string | null;
		userName?: string | null;
		userEmail?: string | null;
		userRole?: string | null;
		conversationId?: string | null;
		hasPii?: boolean;
	};

	let requests: RequestItem[] = [];
	let loading = true;
	let error: string | null = null;
	let page = 1;
	const pageSize = 10;
	let isLastPage = false;
	let searchTerm = '';
	let hasPiiOnly = false;

	const loadPage = async (targetPage: number) => {
		loading = true;
		error = null;

		const safePage = Math.max(1, targetPage);

		loading = true;
		error = null;

		try {
			const params = new URLSearchParams();
			params.set('page', String(safePage));

			const trimmed = searchTerm.trim();
			if (trimmed) {
				params.set('query', trimmed);
			}
			if (hasPiiOnly) {
				params.set('has_pii', 'true');
			}

			const res = await fetch(`${WEBUI_BASE_URL}/api/requests?${params.toString()}`, {
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

			const data = (await res.json()) as RequestItem[];
			requests = Array.isArray(data) ? data : [];
			page = safePage;
			isLastPage = requests.length < pageSize;
		} catch (e: unknown) {
			console.error(e);
			error = e instanceof Error ? e.message : 'Не удалось загрузить данные';
		} finally {
			loading = false;
		}
	};

	onMount(async () => {
		await loadPage(1);
	});
</script>

<div class="px-4.5 w-full mx-auto max-w-5xl py-4 space-y-4">
	<div class="flex flex-wrap gap-3 items-center justify-between">
		<div class="flex flex-1 min-w-[240px] max-w-md items-center gap-2">
			<input
				type="text"
				class="flex-1 px-3 py-1.5 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
				placeholder="Поиск по имени или email…"
				bind:value={searchTerm}
			/>
			<button
				class="inline-flex items-center gap-1 px-3 py-2 rounded border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-xs font-medium hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-default"
				on:click={() => loadPage(1)}
				disabled={loading}
			>
				<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<circle cx="11" cy="11" r="6" />
					<path d="m16 16 4 4" />
				</svg>
				<span>Поиск</span>
			</button>
		</div>

		<label class="inline-flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
			<input
				type="checkbox"
				class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
				bind:checked={hasPiiOnly}
				on:change={() => loadPage(1)}
			/>
			<span>Только с персональными данными</span>
		</label>
	</div>

	{#if error}
		<div class="text-sm text-red-600 dark:text-red-400">
			{error}
		</div>
	{/if}

	{#if loading}
		<div class="text-sm text-gray-400 dark:text-gray-600">Загрузка…</div>
	{:else if requests.length === 0 && !error}
		<div class="text-sm text-gray-400 dark:text-gray-600">Нет данных для отображения.</div>
	{:else}
		<div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
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

		{#each requests as request}
			<div
				class="border border-gray-200 dark:border-gray-800 rounded-xl bg-white dark:bg-gray-900 shadow-sm"
			>
				<div
					class="items-center px-4 py-2 border-b border-gray-100 dark:border-gray-800 text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-x-4 gap-y-1"
				>
					<span>{request.time}</span>
                    {#if request.conversationId}
                      <a
                        href={`/s/${request.conversationId}`}
                        class="inline-flex items-center gap-1 text-white hover:underline underline-offset-2"
                        title="Открыть источник"
                      >
                        Источник
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          class="h-3 w-3 opacity-80"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          stroke-width="2"
                        >
                          <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            d="M13.828 10.172a4 4 0 010 5.656l-3 3a4 4 0 01-5.656-5.656l1.5-1.5m6.828-1.828a4 4 0 010-5.656l3-3a4 4 0 115.656 5.656l-1.5 1.5"
                          />
                        </svg>
                      </a>
                    {:else}
                      <span class="text-gray-400 dark:text-gray-500">Без источника</span>
                    {/if}
					{#if request.userName || request.userEmail || request.userRole}
						<span class="text-gray-600 dark:text-gray-300">
							{request.userName ?? '—'}
							{#if request.userEmail}
								<span class="text-gray-400 dark:text-gray-500">({request.userEmail})</span>
							{/if}
							{#if request.userRole}
								<span class="text-gray-400 dark:text-gray-500">· {request.userRole}</span>
							{/if}
						</span>
					{:else}
						<span class="text-gray-400 dark:text-gray-500">пользователь неизвестен</span>
					{/if}

					{#if request.hasPii}
						<span
							class="px-2 py-0.5 rounded-full bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300 border border-red-100 dark:border-red-900"
						>
							ПДн
						</span>
					{/if}
				</div>

				<div class="px-4 py-3">
					<div class="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-0">
						<div
							class="md:pr-3 border-b md:border-b-0 md:border-r border-gray-100 dark:border-gray-800"
						>
							<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
								Оригинальный текст
							</div>
							<div
								class="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-100 leading-relaxed py-1"
							>
								{request.originalText}
							</div>
						</div>

						<div class="md:pl-3 pt-2 md:pt-0">
							<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
								Заменённый текст
							</div>
							<div
								class="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-100 leading-relaxed py-1"
							>
								{request.modifiedText}
							</div>
						</div>
					</div>
				</div>
			</div>
		{/each}

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

