<script lang="ts">
	import { onMount } from 'svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';

	type RequestItem = {
		time: string;
		chatLink: string;
		originalText: string;
		modifiedText: string;
	};

	let requests: RequestItem[] = [];
	let loading = true;
	let error: string | null = null;

	onMount(async () => {
		loading = true;
		error = null;

		try {
			const res = await fetch(`${WEBUI_BASE_URL}/api/requests`, {
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
		} catch (e: unknown) {
			console.error(e);
			error = e instanceof Error ? e.message : 'Не удалось загрузить данные';
		} finally {
			loading = false;
		}
	});
</script>

<div class="mx-auto max-w-5xl py-4 space-y-4">
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
		{#each requests as request}
			<div
				class="border border-gray-200 dark:border-gray-800 rounded-xl bg-white dark:bg-gray-900 shadow-sm"
			>
				<div
					class="px-4 py-2 border-b border-gray-100 dark:border-gray-800 text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-x-4 gap-y-1"
				>
					<span>{request.time}</span>
					<a href={request.chatLink} class="underline-offset-2 hover:underline">Ссылка</a>
					<span class="text-gray-400 dark:text-gray-500">мета‑данные…</span>
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
	{/if}
</div>