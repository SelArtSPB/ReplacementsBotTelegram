
function xhr(resource, query, cbfunc)
{
	var ts = (new Date()).getTime();
	var req = new XMLHttpRequest();
	req.onreadystatechange = function()
	{
		if (req.readyState != 4) return;
		if (req.status == 200) return cbfunc(req.responseText, 'ok');
		if (req.status == 0) cbfunc('', req.status + ' - connection failed');
		else return cbfunc('', req.status + ' - ' + req.responseText);
	}
	req.open('GET', resource + '?ts=' + ts + query, true);
	try
	{
		req.send();
	}
	catch (ex)
	{
		cbfunc('', 'xhr failure');
	}
}

function update_ready(text, reason)
{
	if (text == '') text = 'error: ' + reason;
	document.getElementById('content').innerHTML = text;
}

function update()
{
	xhr('/replacements/api/fetch-rep', '', update_ready);
}

function main()
{
	update();
}

window.addEventListener('load', main, false);
