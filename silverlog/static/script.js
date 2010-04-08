var app = $.sammy(function () {
  this.element_selector = '#body';

  this.get('#/', function (context) {
    moveScreen('#main');
    $('#main #log-list li:nth-child(1n+2)').remove();
    $('#header #title-slot').text('index');
    $.ajax({
      url: "/api/list-logs",
      dataType: "json",
      success: function (result) {
        $('#main').render(
          result,
          {
            "#log-list li": {
              "log<-logs": {
                "a": "log.description",
                "a@href": function (ctx) {
                  return '#/view/'+ctx.item.id;
                }
              }
            }
          });
      }
    });
  });

  this.get('#/view/:log_id', function (context) {
    moveScreen('#log-view');
    $.ajax({
      url: "/api/log/"+this.params.log_id,
      dataType: "json",
      success: function (result) {
        $('#header #title-slot').text(result.description);
        $('#log-view').render(
          result,
          {
            "pre.content": "content"
          });
      }
    });
  });

});

$(function () {
  app.run('#/');
});

var currentScreen = null;

function moveScreen(selector) {
  if (currentScreen) {
    $(currentScreen).hide();
    currentScreen = null;
  }
  var el = $(selector);
  currentScreen = selector;
  el.show();
  return el;
}
