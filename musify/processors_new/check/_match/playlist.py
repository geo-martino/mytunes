from collections import Counter
from collections.abc import MutableSequence, Collection, Iterable
from copy import copy

from musify.models.properties.uri import HasURI, URI, HasMutableURI
from musify.models.sequence import UniqueSequence
from musify.processors_new.check._match._base import CheckerMatch
from musify.processors_new.check.result import CheckResult


class PlaylistMatch(CheckerMatch):
    async def match[CT: HasURI](self, items: Collection[CT], uri: URI, name: str) -> CheckResult[CT]:
        """Match the given that have missing URIs with items in the current playlist."""
        self.logger.info(f"Checking for changes to items in {self.page.source} playlist: {name}", header=2)

        current = await self.page.get_current_playlist_items(uri)
        added, removed, unchanged, unavailable, missing = self._compare_items(
            items=items, others=current, uri=uri, name=name
        )

        if not added and not removed and not missing:
            message = "Playlist unchanged and no missing URIs, skipping match"
            self._log_debug("SKIP", name, message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=missing)

        missing += removed
        for item in missing:
            if isinstance(item, HasMutableURI):
                del item.uri

        if not missing:
            message = "No items changed in playlist and no items with missing matches, skipping match"
            self._log_debug("SKIP", name, message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable)

        if not added:
            message = "No items added, skipping match"
            self._log_debug("SKIP", name, message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=missing)

        if not any(isinstance(item, HasMutableURI) for item in missing):
            message = "No items with mutable URIs to match with added items, skipping match"
            self._log_debug("SKIP", name, message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=missing)

        changed = self._match_items_with_others(items=missing, others=added, name=name)
        return CheckResult(changed=changed, unchanged=unchanged, unavailable=unavailable, skipped=missing)

    def _compare_items[CT: HasURI, RT: HasURI](
            self,
            items: Collection[CT],
            others: Collection[RT],
            uri: URI,
            name: str,
    ) -> tuple[list[RT], list[CT], list[CT], list[CT], list[CT]]:
        valid_items = self.get_valid_items(items)

        items_unique = UniqueSequence(valid_items)
        others_unique = UniqueSequence(others)

        added = list(others_unique.difference(items_unique))
        removed = list(items_unique.difference(others_unique))
        removed += self._compare_duplicate_items(valid_items, others, removed)
        unchanged = list(items_unique.intersection(others_unique))
        unavailable = self.get_unavailable_items(items)
        missing = self.get_missing_items(items)

        if self.page.use_existing_playlists and (initial := len(self.page.get_initial_playlist_items(uri))) > 0:
            initial_message = "items that were in the playlist before starting"
            self._log_debug("REMOTE", name, initial_message, initial)

        self._log_debug("REMOTE", name, "items at start", len(items))
        self._log_debug("REMOTE", name, "items that are confirmed as unavailable", len(unavailable))
        self._log_debug("REMOTE", name, "items added", len(added))
        self._log_debug("REMOTE", name, "items removed", len(removed))
        self._log_debug("REMOTE", name, "difference", len(added) - len(removed))
        self._log_debug("REMOTE", name, "items unchanged", len(unchanged))
        self._log_debug("REMOTE", name, "items still with missing URI", len(missing))
        self._log_debug("REMOTE", name, "total item changes", len(added) - len(removed))

        return added, removed, unchanged, unavailable, missing

    @staticmethod
    def _compare_duplicate_items[CT: HasURI](
            initial: Collection[CT], others: Iterable[HasURI], unique: list[CT]
    ) -> list[CT]:
        # if item collection originally contained duplicate URIS and one or more of the duplicates were removed
        # find removed duplicate items by looking for changes in counts
        initial_counts = Counter(item.uri for item in initial)
        other_counts = Counter(item.uri for item in others)
        current_counts = Counter(item.uri for item in unique)

        duplicates = []
        for item in initial:
            initial_count = initial_counts.get(item.uri, 0)
            other_count = other_counts.get(item.uri, 0)
            current_count = current_counts.get(item.uri, 0)

            if initial_count == 1 or initial_count <= current_count + other_count:
                continue

            duplicates.append(item)
            current_counts = Counter(item.uri for item in unique + duplicates)  # refresh counts

        return duplicates

    def _match_items_with_others[CT: HasURI](
            self, items: MutableSequence[CT], others: MutableSequence[CT], name: str | None = None
    ) -> list[CT]:
        initial = len(items)
        changed = []

        for item in copy(items):  # copy to safely modify items while iterating
            if not others:
                break

            match = self._match_item_with_others(item, others, "REMOTE")
            if match is None:
                continue

            changed.append(item)
            items.remove(item)
            others.remove(match)

        final = len(items)
        self._log_debug("REMOTE", name, "items switched", initial - final)
        self._log_debug("REMOTE", name, "items still not found", final)

        return changed
