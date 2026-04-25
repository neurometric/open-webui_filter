<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { marked } from 'marked';

	import { onMount, getContext, tick, createEventDispatcher } from 'svelte';
	import { blur, fade } from 'svelte/transition';

	const dispatch = createEventDispatcher();

	import { getChatList } from '$lib/apis/chats';
	import { updateFolderById } from '$lib/apis/folders';

	import {
		config,
		user,
		models as _models,
		temporaryChatEnabled,
		selectedFolder,
		chats,
		currentChatPage
	} from '$lib/stores';
	import { sanitizeResponseContent, extractCurlyBraceWords } from '$lib/utils';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';

	import Suggestions from './Suggestions.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import MessageInput from './MessageInput.svelte';
	import FolderPlaceholder from './Placeholder/FolderPlaceholder.svelte';
	import FolderTitle from './Placeholder/FolderTitle.svelte';

	const i18n = getContext('i18n');

	export let createMessagePair: Function;
	export let stopResponse: Function;

	export let autoScroll = false;

	export let atSelectedModel: Model | undefined;
	export let selectedModels: [''];

	export let history;

	export let prompt = '';
	export let files = [];
	export let messageInput = null;

	export let selectedToolIds = [];
	export let selectedFilterIds = [];

	export let showCommands = false;

	export let imageGenerationEnabled = false;
	export let codeInterpreterEnabled = false;
	export let webSearchEnabled = false;

	export let onSelect = (e) => {};
	export let onChange = (e) => {};

	export let toolServers = [];
	export let disabled = false;
	let models = [];
	let selectedModelIdx = 0;

	$: if (selectedModels.length > 0) {
		selectedModelIdx = models.length - 1;
	}

	$: models = selectedModels.map((id) => $_models.find((m) => m.id === id));
</script>

<div class="m-auto w-full max-w-6xl px-2 @2xl:px-20 translate-y-6 py-24 text-center">
	{#if $temporaryChatEnabled}
		<Tooltip
			content={$i18n.t("This chat won't appear in history and your messages will not be saved.")}
			className="w-full flex justify-center mb-0.5"
			placement="top"
		>
			<div class="flex items-center gap-2 text-gray-500 text-base my-2 w-fit">
				<EyeSlash strokeWidth="2.5" className="size-4" />{$i18n.t('Temporary Chat')}
			</div>
		</Tooltip>
	{/if}

	<div
		class="w-full text-3xl text-gray-800 dark:text-gray-100 text-center flex items-center gap-4 font-primary"
	>
		<div class="w-full flex flex-col justify-center items-center">
			{#if $selectedFolder}
				<FolderTitle
					folder={$selectedFolder}
					onUpdate={async (folder) => {
						await chats.set(await getChatList(localStorage.token, $currentChatPage));
						currentChatPage.set(1);
					}}
					onDelete={async () => {
						await chats.set(await getChatList(localStorage.token, $currentChatPage));
						currentChatPage.set(1);

						selectedFolder.set(null);
					}}
				/>
			{:else}
				<div class="flex justify-center items-center w-full px-5 max-w-xl">
					<div
						class="flex items-center justify-center w-16 h-16 rounded-full bg-white border border-gray-200 shadow-sm"
					>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="8580 12389.38 4170 3139.12"
                      class="h-5 w-auto"
                      style="color:#0E46FF"
                      aria-hidden="true"
                    >
                      <g fill="currentColor" fill-rule="nonzero">
                        <path d="M8844.34 14528.5c42.1,-9.57 96.21,-27.21 158.3,-57.95 10.53,-5.04 21.06,-10.58 32.07,-16.63 32.57,-17.64 340.15,-206.1 438.34,-265.56 128.74,-79.12 248.47,-153.7 305.09,-188.47 136.23,-84.15 236.93,-186.95 464.37,-168.31 238.94,19.15 494.93,226.26 536.02,255.99 12.51,8.07 802.5,608.23 942.28,685.33 250.99,137.07 384.73,70.05 500.44,28.72 -173.33,163.27 -413.78,299.34 -413.78,299.34 -185.35,114.38 -407.78,112.37 -592.12,-4.05 0,0 -524,-444.95 -898.71,-697.91 -1,-0.51 -2.01,-1.01 -2.99,-2.02 -158.3,-99.78 -361.21,-93.23 -516.49,11.09 -207.88,140.09 -410.29,276.64 -410.29,276.64 -125.23,79.12 -276.01,80.13 -401.74,2.53l-238.47 -147.15c0,0 36.09,2.02 97.21,-12.6z"/>
                        <path d="M8999.15 13193.12c0,0 -46.59,13.61 -46.59,209.63l0 768.98c0,133.54 30.05,187.96 41.56,204.08 3.02,4.04 5.03,5.55 5.03,5.55 0,0 -15.03,8.56 -38.07,20.66 -50.11,26.2 -139.78,67.52 -204.39,67.52 -93.69,0 -176.34,-92.21 -176.34,-206.1l0 -953.41c0,-113.88 82.65,-206.1 176.34,-206.1 93.66,0 241.96,88.69 241.96,88.69z"/>
                        <path d="M10977.39 13358.91c-115.73,74.08 -195.87,125.98 -199.37,128.5 -40.58,29.73 -297.07,236.34 -536.02,255.99 -227.43,18.64 -328.13,-84.15 -464.39,-168.31 -135.76,-84.15 -647.73,-402.13 -742.9,-454.53 -170.34,-93.23 -287.55,-87.18 -287.55,-87.18l237.94 -146.64c125.76,-77.6 277.05,-76.6 401.77,2.52 0,0 329.62,222.73 577.11,388.52 10.5,7.06 21.54,12.6 32.54,17.13 152.8,87.68 346.16,140.09 556.56,140.09 153.3,0 298.08,-27.71 424.31,-76.59z"/>
                        <path d="M11720.81 12802.08c-58.63,32.25 -407.27,322.01 -658.25,429.84 -250.99,107.84 -316.6,123.46 -508.98,123.46 -144.76,0 -280.01,-26.2 -397.75,-71.55 3.52,-2.02 7.01,-4.03 10.03,-6.05 244.95,-166.29 1069.52,-799.72 1069.52,-799.72 184.36,-116.4 386.74,-117.91 572.09,-4.03 0,0 240.45,136.56 413.78,299.33 -115.71,-41.32 -249.48,-108.34 -500.44,28.72z"/>
                        <path d="M12403.6 14324.42c0,214.66 -188.86,411.19 -371.21,411.19 -259.98,0 -396.75,-133.03 -396.75,-133.03 0,0 311.1,-69.04 311.1,-473.18l0 -684.32c0,-404.14 -311.1,-473.18 -311.1,-473.18 0,0 137.27,-133.03 396.75,-133.03 182.35,0 371.21,196.52 371.21,411.19l0 1074.86z"/>
                      </g>
                    </svg>
					</div>
				</div>

				<div class="flex mt-1 mb-2">
					<div in:fade={{ duration: 100, delay: 50 }}>
						{#if models[selectedModelIdx]?.info?.meta?.description ?? null}
							<Tooltip
								className=" w-fit"
								content={marked.parse(
									sanitizeResponseContent(
										models[selectedModelIdx]?.info?.meta?.description ?? ''
									).replaceAll('\n', '<br>')
								)}
								placement="top"
							>
								<div
									class="mt-0.5 px-2 text-sm font-normal text-gray-500 dark:text-gray-400 line-clamp-2 max-w-xl markdown"
								>
									{@html marked.parse(
										sanitizeResponseContent(
											models[selectedModelIdx]?.info?.meta?.description ?? ''
										).replaceAll('\n', '<br>')
									)}
								</div>
							</Tooltip>

							{#if models[selectedModelIdx]?.info?.meta?.user}
								<div class="mt-0.5 text-sm font-normal text-gray-400 dark:text-gray-500">
									By
									{#if models[selectedModelIdx]?.info?.meta?.user.community}
										<a
											href="https://openwebui.com/m/{models[selectedModelIdx]?.info?.meta?.user
												.username}"
											>{models[selectedModelIdx]?.info?.meta?.user.name
												? models[selectedModelIdx]?.info?.meta?.user.name
												: `@${models[selectedModelIdx]?.info?.meta?.user.username}`}</a
										>
									{:else}
										{models[selectedModelIdx]?.info?.meta?.user.name}
									{/if}
								</div>
							{/if}
						{/if}
					</div>
				</div>
			{/if}

			<div class="text-base font-normal @md:max-w-3xl w-full py-3 {atSelectedModel ? 'mt-2' : ''}">
				<MessageInput
					bind:this={messageInput}
					{history}
					{selectedModels}
					bind:files
					bind:prompt
					bind:autoScroll
					bind:selectedToolIds
					bind:selectedFilterIds
					bind:imageGenerationEnabled
					bind:codeInterpreterEnabled
					bind:webSearchEnabled
					bind:atSelectedModel
					bind:showCommands
					{toolServers}
					{stopResponse}
					{createMessagePair}
					placeholder={$i18n.t('How can I help you today?')}
					{onChange}
					on:upload={(e) => {
						dispatch('upload', e.detail);
					}}
					on:submit={(e) => {
						dispatch('submit', e.detail);
					}}

				/>
			</div>
		</div>
	</div>

	{#if $selectedFolder}
		<div
			class="mx-auto px-4 md:max-w-3xl md:px-6 font-primary min-h-62"
			in:fade={{ duration: 200, delay: 200 }}
		>
			<FolderPlaceholder folder={$selectedFolder} />
		</div>
	{:else}
		<div class="mx-auto max-w-2xl font-primary mt-2" in:fade={{ duration: 200, delay: 200 }}>
			<div class="mx-5">
				<Suggestions
					suggestionPrompts={atSelectedModel?.info?.meta?.suggestion_prompts ??
						models[selectedModelIdx]?.info?.meta?.suggestion_prompts ??
						$config?.default_prompt_suggestions ??
						[]}
					inputValue={prompt}
					{onSelect}
				/>
			</div>
		</div>
	{/if}
</div>
