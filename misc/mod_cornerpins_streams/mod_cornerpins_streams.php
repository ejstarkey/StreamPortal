<?php defined('_JEXEC') or die;
use Joomla\CMS\HTML\HTMLHelper;
HTMLHelper::_('jquery.framework');
use Joomla\CMS\Factory;
use Joomla\CMS\Uri\Uri;

$document = Factory::getDocument();
$document->addStyleSheet(Uri::base() . 'modules/mod_cornerpins_streams/assets/css/streams.css');

$api_url = $params->get('api_url', 'https://mighty-dassie-rightly.ngrok-free.app/api/streams'); ?>
<div id="cornerpins-streams">
    <h2>Live Streams</h2>
    <div id="stream-tiles" class="stream-tiles"></div>
</div>
<script defer>
jQuery(document).ready(function($) { 
    <?php include 'modules/mod_cornerpins_streams/assets/js/streams.js'; ?>
    loadStreams('<?php echo $api_url; ?>');
});
</script>