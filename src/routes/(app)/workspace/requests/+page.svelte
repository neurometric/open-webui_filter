<script lang="ts">
	const requests = [
		{
			time: '12:34',
			chatLink: 'чат #123',
			originalText: 'Привет, как дела?\nЧто нового?\nПока!',
			modifiedText: 'Привет! Как дела?\nЧто у тебя нового?\nДо встречи!'
		},
		{
			time: '13:15',
			chatLink: 'чат #456',
			originalText: 'Давай встретимся завтра.\nВ 18:00 у кафе.',
			modifiedText: "Предлагаю встретиться завтра.\nВ 18:00 возле кафе 'Уют'."
		},
		{
			time: '14:00',
			chatLink: 'чат #789',
			originalText: 'Отправь файл.\nЖду ответ.',
			modifiedText: 'Можешь отправить файл?\nБуду ждать твой ответ.'
		}
	];
</script>

<div class="mx-auto max-w-5xl py-4 space-y-4">
	{#each requests as request}
		<div class="border border-gray-200 dark:border-gray-800 rounded-xl bg-white dark:bg-gray-900 shadow-sm">
			<div
				class="px-4 py-2 border-b border-gray-100 dark:border-gray-800 text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-x-4 gap-y-1"
			>
				<span>{request.time}</span>
				<a href="#" class="underline-offset-2 hover:underline">{request.chatLink}</a>
				<span class="text-gray-400 dark:text-gray-500">мета‑данные…</span>
			</div>

			<div class="px-4 py-3">
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-0">
					<div class="md:pr-3 border-b md:border-b-0 md:border-r border-gray-100 dark:border-gray-800">
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
</div>


